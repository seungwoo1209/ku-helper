from enum import StrEnum

from app.core.exceptions import AppException


class AuthErrorCode(StrEnum):
    INVALID_OAUTH_STATE = "INVALID_OAUTH_STATE"
    DISCORD_TOKEN_EXCHANGE_FAILED = "DISCORD_TOKEN_EXCHANGE_FAILED"
    DISCORD_USER_FETCH_FAILED = "DISCORD_USER_FETCH_FAILED"
    DISCORD_GUILD_JOIN_FAILED = "DISCORD_GUILD_JOIN_FAILED"


class InvalidOAuthState(AppException):
    code = AuthErrorCode.INVALID_OAUTH_STATE.value
    detail = "OAuth state 값이 유효하지 않거나 만료되었습니다."
    status_code = 401


class DiscordTokenExchangeFailed(AppException):
    code = AuthErrorCode.DISCORD_TOKEN_EXCHANGE_FAILED.value
    detail = "Discord 토큰 교환에 실패했습니다."
    status_code = 502


class DiscordUserFetchFailed(AppException):
    code = AuthErrorCode.DISCORD_USER_FETCH_FAILED.value
    detail = "Discord 사용자 정보를 가져오지 못했습니다."
    status_code = 502


class DiscordGuildJoinFailed(AppException):
    code = AuthErrorCode.DISCORD_GUILD_JOIN_FAILED.value
    detail = "Discord 길드 가입에 실패했습니다."
    status_code = 502
