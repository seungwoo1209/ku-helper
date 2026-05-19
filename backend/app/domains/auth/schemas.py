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
        description="자체 발급 refresh JWT. 만료 30일. access 갱신 전용 (F-05).",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    token_type: str = Field(
        default="bearer",
        description="OAuth2 표준 토큰 타입. 항상 `bearer`.",
        examples=["bearer"],
    )
