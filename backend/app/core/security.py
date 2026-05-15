from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any
from uuid import uuid4

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException

if TYPE_CHECKING:
    from app.domains.users.models import User


_bearer_scheme = HTTPBearer(auto_error=False)


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    STATE = "state"


class InvalidAuthToken(AppException):
    code = "INVALID_AUTH_TOKEN"
    detail = "유효하지 않은 인증 토큰입니다."
    status_code = 401


class AuthTokenMissing(AppException):
    code = "AUTH_TOKEN_MISSING"
    detail = "인증 토큰이 필요합니다."
    status_code = 401


class CurrentUserNotFound(AppException):
    code = "CURRENT_USER_NOT_FOUND"
    detail = "토큰에 해당하는 사용자가 없습니다."
    status_code = 401


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict[str, Any], settings: Settings) -> str:
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def _decode(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )


def create_access_token(user_id: int, discord_id: int) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "sub": str(user_id),
        "discord_id": discord_id,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=settings.jwt_access_expiry_minutes)).timestamp()
        ),
        "jti": uuid4().hex,
        "typ": TokenType.ACCESS.value,
    }
    return _encode(payload, settings)


def create_refresh_token(user_id: int, discord_id: int) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "sub": str(user_id),
        "discord_id": discord_id,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(days=settings.jwt_refresh_expiry_days)).timestamp()
        ),
        "jti": uuid4().hex,
        "typ": TokenType.REFRESH.value,
    }
    return _encode(payload, settings)


def create_state_token() -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=settings.jwt_state_expiry_minutes)).timestamp()
        ),
        "jti": uuid4().hex,
        "typ": TokenType.STATE.value,
    }
    return _encode(payload, settings)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = _decode(token, settings)
    except jwt.PyJWTError as exc:
        raise InvalidAuthToken() from exc
    if payload.get("typ") != expected_type.value:
        raise InvalidAuthToken()
    return payload


def verify_state_token(token: str) -> None:
    decode_token(token, TokenType.STATE)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> "User":
    # UserRepository는 호출 시점에 import (모듈 로드 시 도메인 결합 회피).
    from app.domains.users.dependencies import get_user_repository
    from app.core.database import async_session_maker

    if credentials is None:
        raise AuthTokenMissing()
    payload = decode_token(credentials.credentials, TokenType.ACCESS)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidAuthToken() from exc

    async with async_session_maker() as session:
        repository = get_user_repository(session)
        user = await repository.get_by_id(user_id)
    if user is None:
        raise CurrentUserNotFound()
    return user
