class LunchCrawlerFailed(Exception):
    """학식 페이지 크롤링 실패. Playwright 타임아웃·셀렉터 미일치·파싱 오류 등."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
