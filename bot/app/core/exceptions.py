class BotException(Exception):
    code: str = "BOT_ERROR"
    detail: str = "봇 내부 오류가 발생했습니다."

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)
