from enum import StrEnum

from app.core.exceptions import AppException


class UsersErrorCode(StrEnum):
    USER_NOT_FOUND = "USER_NOT_FOUND"


class UserNotFound(AppException):
    code = UsersErrorCode.USER_NOT_FOUND.value
    detail = "사용자를 찾을 수 없습니다."
    status_code = 404
