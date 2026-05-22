from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    """현재 로그인한 사용자 프로필.

    `discord_id` 는 Discord 의 64-bit Snowflake. 동일 Discord 계정이 탈퇴 후
    재로그인하면 같은 `id`/`discord_id` 로 status 만 ACTIVE 복귀한다.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 42,
                    "discord_id": 123456789012345678,
                    "discord_username": "kustudent",
                    "created_at": "2026-01-15T12:34:56+00:00",
                    "updated_at": "2026-05-20T03:21:09+00:00",
                }
            ]
        },
    )

    id: int = Field(
        description="ku-helper 자체 PK. 우리 서버 안에서만 의미가 있다.",
        examples=[42],
    )
    discord_id: int = Field(
        description="Discord Snowflake (64-bit). DM 발송·OAuth 식별에 쓰인다.",
        examples=[123456789012345678],
    )
    discord_username: str = Field(
        description="로그인 시점에 캐시한 Discord 사용자명. 갱신은 재로그인 시.",
        examples=["kustudent"],
    )
    created_at: datetime = Field(
        description="레코드 최초 생성 시각 (ISO 8601, UTC).",
    )
    updated_at: datetime = Field(
        description="마지막 갱신 시각. 재로그인·소프트 삭제·복귀 시 변경된다.",
    )


class UserUpdate(BaseModel):
    """PATCH /users/me 본문. 현재 미구현 — 정책 미결로 수정 가능 필드가 없다.

    후속 PR (백엔드 roadmap A-1) 에서 `discord_username` 캐시 동기화 등을 정의한다.
    """

    # TODO: 수정 가능한 필드는 후속 PR에서 정의.
    pass
