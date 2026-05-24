from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    # DB · Redis 접근 모드. 로컬 dev/test 는 URL 방식, AWS 운영은 IAM 토큰 방식.
    use_iam_auth: bool = False
    aws_region: str = "ap-northeast-2"

    database_url: str = ""
    redis_url: str = ""

    # IAM 모드 전용 (use_iam_auth=True 일 때 필수). 인프라(SSM Parameter Store) 가 주입.
    db_host: str = ""
    db_port: int = 5432
    db_name: str = ""
    db_iam_user: str = ""
    redis_host: str = ""
    redis_port: int = 6379
    redis_iam_user: str = ""
    redis_cache_name: str = ""

    cors_origins: list[str] = Field(default_factory=list)

    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_access_expiry_minutes: int = 30
    jwt_refresh_expiry_days: int = 30
    jwt_state_expiry_minutes: int = 5

    discord_client_id: str
    discord_client_secret: SecretStr
    discord_bot_token: SecretStr
    discord_redirect_uri: str
    discord_oauth_scopes: list[str] = Field(
        # applications.commands는 user-install이 자동 성립하도록 유도.
        # 이후 50278(mutual guilds 없음)로 인한 DM 실패가 사라지는지 가설 검증 중.
        default_factory=lambda: ["identify", "applications.commands"]
    )
    # 1 = USER_INSTALL (Discord 사용자 계정 설치), 0 = GUILD_INSTALL.
    # 사용자 설치 흐름으로 통일하므로 기본값은 1.
    discord_integration_type: int = 1

    frontend_url: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _validate_db_redis_inputs(self) -> Self:
        if self.use_iam_auth:
            missing = [
                name
                for name in (
                    "db_host",
                    "db_name",
                    "db_iam_user",
                    "redis_host",
                    "redis_iam_user",
                    "redis_cache_name",
                )
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(
                    f"USE_IAM_AUTH=true requires non-empty: {', '.join(missing)}"
                )
        else:
            if not self.database_url:
                raise ValueError("DATABASE_URL is required when USE_IAM_AUTH=false")
            if not self.redis_url:
                raise ValueError("REDIS_URL is required when USE_IAM_AUTH=false")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
