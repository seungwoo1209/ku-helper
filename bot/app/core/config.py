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

    discord_bot_token: SecretStr

    # F-22 관리자 알림 대상. 화이트리스트는 정적 관리.
    admin_discord_ids: list[int] = Field(default_factory=list)

    # §B(교통 알림)에서 필수화. 현재는 None 허용.
    subway_api_key: SecretStr | None = None

    # §C(점심 알림) — Naver Local Search API 키. RestaurantsClient 가 사용.
    # 미설정 시 RestaurantsClient 가 즉시 RestaurantsCrawlerFailed 를 던진다.
    naver_search_client_id: str | None = None
    naver_search_client_secret: SecretStr | None = None

    # 건국대 학식 페이지 URL. LunchClient 가 Playwright 로 크롤링.
    cafeteria_url: str = "https://www.konkuk.ac.kr/general/18211/subview.do"

    # §D 도서관 좌석 API. example-response.json 형태의 JSON 을 반환하는 엔드포인트.
    # 미설정 시 LibraryClient 가 즉시 LibraryCrawlerFailed 를 던지고 library worker 는 skip.
    library_seat_url: str | None = None

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
