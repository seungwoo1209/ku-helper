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

    # §0 부트스트랩 단계에서는 Redis 없이도 기동 가능하도록 옵셔널.
    # §A(Sender)에서 캐시·쿨다운 키가 도입되면 필수화한다.
    redis_url: str | None = None

    discord_bot_token: SecretStr

    # F-22 관리자 알림 대상. 화이트리스트는 정적 관리.
    admin_discord_ids: list[int] = Field(default_factory=list)

    # §B(교통 알림)에서 필수화. 현재는 None 허용.
    subway_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
