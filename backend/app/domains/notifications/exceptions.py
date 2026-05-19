from enum import StrEnum

from app.core.exceptions import AppException


class NotificationsErrorCode(StrEnum):
    NOTIFICATION_NOT_FOUND = "NOTIFICATION_NOT_FOUND"
    NOTIFICATION_FORBIDDEN = "NOTIFICATION_FORBIDDEN"


class NotificationNotFound(AppException):
    code = NotificationsErrorCode.NOTIFICATION_NOT_FOUND.value
    detail = "알림 설정을 찾을 수 없습니다."
    status_code = 404


class NotificationForbidden(AppException):
    code = NotificationsErrorCode.NOTIFICATION_FORBIDDEN.value
    detail = "해당 알림 설정에 접근할 권한이 없습니다."
    status_code = 403
