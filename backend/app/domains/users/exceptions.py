from enum import StrEnum

from app.core.exceptions import AppException


class UsersErrorCode(StrEnum):
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_DELETED = "USER_DELETED"


class UserNotFound(AppException):
    code = UsersErrorCode.USER_NOT_FOUND.value
    detail = "사용자를 찾을 수 없습니다."
    status_code = 404


class UserDeleted(AppException):
    code = UsersErrorCode.USER_DELETED.value
    detail = "삭제된 사용자입니다."
    status_code = 401
