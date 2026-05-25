"""AWS IAM 인증으로 RDS PostgreSQL · ElastiCache Valkey 접속할 때 사용할 토큰 발급 헬퍼.

- RDS: `boto3` `RDS.generate_db_auth_token` (15분 유효).
- ElastiCache: SigV4 query 서명된 PreSigned URL 의 path+query 가 그대로 password 가 된다 (AWS 공식 패턴).

토큰은 매 연결 시점에 새로 발급한다. 만료가 짧고 connection pool 재사용 시
SQLAlchemy `do_connect` 이벤트 / redis-py `CredentialProvider` 가 트리거한다.
"""

from __future__ import annotations

import boto3
from botocore.auth import SigV4QueryAuth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession

_ELASTICACHE_TOKEN_TTL_SECONDS = 900


def generate_rds_iam_token(*, host: str, port: int, user: str, region: str) -> str:
    client = boto3.client("rds", region_name=region)
    # boto3 stubs 미제공 → Any 반환. str() 로 좁혀 mypy no-any-return 를 회피한다.
    return str(
        client.generate_db_auth_token(
            DBHostname=host,
            Port=port,
            DBUsername=user,
            Region=region,
        )
    )


def generate_elasticache_iam_token(
    *, cache_name: str, user_id: str, region: str
) -> str:
    """ElastiCache Valkey IAM 토큰.

    AWS 공식 패턴: `https://<cache_name>/?Action=connect&User=<user>` 에 SigV4 query
    서명을 붙인 뒤 `http(s)://` prefix 만 제거한 문자열을 그대로 password 로 사용한다.
    """
    session = BotocoreSession()
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("AWS credentials not available for ElastiCache IAM auth")

    request = AWSRequest(
        method="GET",
        url=f"http://{cache_name}/",
        params={"Action": "connect", "User": user_id},
    )
    SigV4QueryAuth(
        credentials=credentials,
        service_name="elasticache",
        region_name=region,
        expires=_ELASTICACHE_TOKEN_TTL_SECONDS,
    ).add_auth(request)
    # botocore stubs 미제공 → request.url 이 Any. str() 로 좁혀 mypy no-any-return 회피.
    return str(request.url).removeprefix("http://")
