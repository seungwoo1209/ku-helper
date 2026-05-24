from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis, from_url
from redis.credentials import CredentialProvider

from app.core.aws_auth import generate_elasticache_iam_token
from app.core.config import Settings


class _ElastiCacheIamCredentialProvider(CredentialProvider):
    """redis-py 가 매 connect 시 호출. SigV4 토큰의 15분 만료 안에 재사용 안전."""

    def __init__(self, *, cache_name: str, user_id: str, region: str) -> None:
        self._cache_name = cache_name
        self._user_id = user_id
        self._region = region

    def get_credentials(self) -> tuple[str, str]:
        token = generate_elasticache_iam_token(
            cache_name=self._cache_name,
            user_id=self._user_id,
            region=self._region,
        )
        return (self._user_id, token)


async def create_redis_client(settings: Settings) -> Redis:
    client: Redis
    if settings.use_iam_auth:
        client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            ssl=True,
            decode_responses=True,
            credential_provider=_ElastiCacheIamCredentialProvider(
                cache_name=settings.redis_cache_name,
                user_id=settings.redis_iam_user,
                region=settings.aws_region,
            ),
        )
    else:
        client = from_url(settings.redis_url, decode_responses=True)
    # redis-py 의 ping 은 sync/async overload 라 mypy 가 union 을 본다. 비동기
    # 클라이언트라 실제로는 Awaitable[bool] 임이 보장되어 cast 로 좁힌다.
    await cast(Awaitable[bool], client.ping())
    return client
