class RestaurantsCrawlerFailed(Exception):
    """네이버 지역 검색 API 호출 실패. HTTP 4xx/5xx·인증 누락 등."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
