from functools import lru_cache

from pydantic import Field, SecretStr
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

    database_url: str
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
    discord_oauth_scopes: list[str] = Field(default_factory=lambda: ["identify"])
    # 1 = USER_INSTALL (Discord 사용자 계정 설치), 0 = GUILD_INSTALL.
    # 사용자 설치 흐름으로 통일하므로 기본값은 1.
    discord_integration_type: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
