from enum import StrEnum

from app.core.exceptions import AppException


class ImmediateSendErrorCode(StrEnum):
    IMMEDIATE_SEND_RATE_LIMITED = "IMMEDIATE_SEND_RATE_LIMITED"


class ImmediateSendRateLimited(AppException):
    code = ImmediateSendErrorCode.IMMEDIATE_SEND_RATE_LIMITED.value
    detail = "잠시 후 다시 시도해주세요."
    status_code = 429
