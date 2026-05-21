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

    # 외부 API 캐시·LIBRARY 상태머신·TRANSIT arrival dedup 공용. 미설정 시 봇 기동 실패.
    redis_url: str

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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
