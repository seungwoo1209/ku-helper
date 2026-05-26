from enum import StrEnum

from app.core.exceptions import AppException


class NotificationsErrorCode(StrEnum):
    NOTIFICATION_NOT_FOUND = "NOTIFICATION_NOT_FOUND"
    NOTIFICATION_FORBIDDEN = "NOTIFICATION_FORBIDDEN"
    INVALID_HISTORY_DATE_RANGE = "INVALID_HISTORY_DATE_RANGE"


class NotificationNotFound(AppException):
    code = NotificationsErrorCode.NOTIFICATION_NOT_FOUND.value
    detail = "알림 설정을 찾을 수 없습니다."
    status_code = 404


class NotificationForbidden(AppException):
    code = NotificationsErrorCode.NOTIFICATION_FORBIDDEN.value
    detail = "해당 알림 설정에 접근할 권한이 없습니다."
    status_code = 403


class InvalidHistoryDateRange(AppException):
    # F-17 알림 발송 이력 조회의 30일 상한·역순 범위 거절. 422 는 본문이 아니라 query
    # 파라미터 의미 오류를 가리킨다(FastAPI 의 형식 오류 422 와 의도적으로 같은 상태).
    code = NotificationsErrorCode.INVALID_HISTORY_DATE_RANGE.value
    detail = (
        "조회 기간이 올바르지 않습니다. date_from 은 date_to 보다 이전이어야 하며, "
        "범위는 최대 30일까지만 허용됩니다."
    )
    status_code = 422
