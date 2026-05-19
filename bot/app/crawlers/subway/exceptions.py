from app.core.exceptions import BotException


class SubwayApiUnavailable(BotException):
    code = "SUBWAY_API_UNAVAILABLE"
    detail = "지하철 API 가 일시적으로 응답하지 않습니다."


class SubwayApiAuthFailed(BotException):
    code = "SUBWAY_API_AUTH_FAILED"
    detail = "지하철 API 인증 키가 유효하지 않습니다."
