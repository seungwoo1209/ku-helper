from app.core.exceptions import BotException


class RestaurantsCrawlerFailed(BotException):
    """네이버 지역 검색 API 호출 실패. HTTP 4xx/5xx·인증 누락 등."""

    code = "RESTAURANTS_CRAWLER_FAILED"
    detail = "음식점 정보를 가져오지 못했습니다."

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(self.detail)
