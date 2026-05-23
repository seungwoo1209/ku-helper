from collections.abc import Awaitable
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, cast
from uuid import uuid4

import jwt
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException

# Redis key prefix for refresh-token whitelist (jti -> user_id). 발급 시 SETEX,
# 로그아웃·rotation 시 DEL. 키가 없으면 그 refresh 는 사용 불가.
_REFRESH_JTI_KEY = "refresh_jti:{jti}"

# OAuth state token 1회용화 키. 콜백 진입 시 SET NX 으로 잠그고, 두 번째 시도는 NX 실패.
# JWT 만료(jwt_state_expiry_minutes)와 동일 TTL — 만료 이후에는 JWT 검증이 먼저 거절한다.
_STATE_USED_KEY = "state_used:{jti}"


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


class NotAuthorizedForRole(AppException):
    code = "NOT_AUTHORIZED_FOR_ROLE"
    detail = "필요한 권한이 없습니다."
    status_code = 403


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


def create_refresh_token(user_id: int, discord_id: int) -> tuple[str, str]:
    """refresh JWT 와 그 jti 를 함께 반환. 호출 측이 jti 를 Redis whitelist 에 등록한다."""
    settings = get_settings()
    now = _now()
    jti = uuid4().hex
    payload = {
        "sub": str(user_id),
        "discord_id": discord_id,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(days=settings.jwt_refresh_expiry_days)).timestamp()
        ),
        "jti": jti,
        "typ": TokenType.REFRESH.value,
    }
    return _encode(payload, settings), jti


async def register_refresh_jti(redis: Redis, jti: str, user_id: int) -> None:
    settings = get_settings()
    ttl_seconds = settings.jwt_refresh_expiry_days * 86400
    await cast(
        Awaitable[bool],
        redis.set(_REFRESH_JTI_KEY.format(jti=jti), str(user_id), ex=ttl_seconds),
    )


async def revoke_refresh_jti(redis: Redis, jti: str) -> None:
    # DEL 은 키가 없어도 무해 — logout idempotent 보장.
    await cast(Awaitable[int], redis.delete(_REFRESH_JTI_KEY.format(jti=jti)))


async def assert_refresh_jti_active(redis: Redis, jti: str) -> None:
    exists = await cast(Awaitable[int], redis.exists(_REFRESH_JTI_KEY.format(jti=jti)))
    if not exists:
        raise InvalidAuthToken()


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


def verify_state_token(token: str) -> dict[str, Any]:
    return decode_token(token, TokenType.STATE)


async def consume_state_jti(redis: Redis, jti: str) -> None:
    """state jti 를 1회용으로 마킹. SET NX 가 실패하면 이미 사용된 state → InvalidAuthToken.

    TTL 은 settings.jwt_state_expiry_minutes 와 동일. JWT 자체 만료가 그 이전에 거절하므로
    더 길게 보관할 이유 없음.
    """
    settings = get_settings()
    ttl_seconds = settings.jwt_state_expiry_minutes * 60
    ok = await cast(
        Awaitable[bool | None],
        redis.set(_STATE_USED_KEY.format(jti=jti), "1", nx=True, ex=ttl_seconds),
    )
    if not ok:
        raise InvalidAuthToken()


