from pydantic import BaseModel, ConfigDict, Field


class TokenRead(BaseModel):
    """Discord OAuth 콜백 성공 시 발급되는 자체 JWT 쌍.

    `access_token` 은 보호 엔드포인트의 `Authorization: Bearer ...` 헤더로 사용한다.
    `refresh_token` 은 access 갱신 전용 (F-05, 후속 PR). 두 토큰 모두 HS256 서명,
    payload = (sub=user_id, discord_id, exp, iat, jti).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                }
            ]
        },
    )

    access_token: str = Field(
        description="자체 발급 access JWT. 만료 30분. 보호 엔드포인트에 Bearer 로 전달.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    refresh_token: str = Field(
        description=(
            "자체 발급 refresh JWT. 만료 30일. `POST /auth/refresh` 로 새 access·refresh "
            "교환에만 사용. jti 가 Redis whitelist 에 등록돼 있어야 통과한다."
        ),
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    token_type: str = Field(
        default="bearer",
        description="OAuth2 표준 토큰 타입. 항상 `bearer`.",
        examples=["bearer"],
    )


class TokenRefreshRequest(BaseModel):
    """`POST /auth/refresh` 요청 본문.

    클라이언트는 보관 중인 refresh JWT 를 body 로 보낸다. 서버는 jti whitelist 를 확인한 뒤
    rotation(old jti DEL + new jti SET) 후 새 access·refresh 쌍을 반환한다. 같은 refresh 를
    두 번 사용하면 두 번째 호출은 401(INVALID_AUTH_TOKEN)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}]
        },
    )

    refresh_token: str = Field(
        description="이전 로그인/refresh 응답으로 받은 refresh JWT.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )


class LogoutRequest(BaseModel):
    """`POST /auth/logout` 요청 본문.

    refresh jti 를 Redis whitelist 에서 제거해 추가 refresh 시도를 차단한다. 같은 토큰으로
    두 번 호출해도 204 (DEL 은 idempotent). access 토큰은 별도 블랙리스트가 없으므로 만료
    시까지 유효한 채 남는다(access 만료 30분)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}]
        },
    )

    refresh_token: str = Field(
        description="로그아웃 대상 refresh JWT.",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
