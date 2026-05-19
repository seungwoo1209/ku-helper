class AppException(Exception):
    code: str = "APP_ERROR"
    detail: str = "내부 오류가 발생했습니다."
    status_code: int = 500

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)
