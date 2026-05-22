from app.core.exceptions import BotException


class LunchCrawlerFailed(BotException):
    """학식 페이지 크롤링 실패. Playwright 타임아웃·셀렉터 미일치·파싱 오류 등."""

    code = "LUNCH_CRAWLER_FAILED"
    detail = "학식 정보를 가져오지 못했습니다."

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(self.detail)
