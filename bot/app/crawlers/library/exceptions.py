from app.core.exceptions import BotException


class LibraryCrawlerFailed(BotException):
    code = "LIBRARY_CRAWLER_FAILED"
    detail = "도서관 좌석 정보를 가져오지 못했습니다."

    def __init__(self, reason: str | None = None) -> None:
        # reason 은 로깅용 세부 사유(영문). detail 은 사용자 노출용 한국어.
        self.reason = reason or self.code
        super().__init__(self.detail)
