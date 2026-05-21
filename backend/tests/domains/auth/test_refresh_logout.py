"""F-02/F-05 refresh·logout 회귀 가드.

핵심 불변:
- /auth/refresh 는 jti 가 Redis whitelist 에 있을 때만 통과 + rotation 후 old jti 삭제.
- 같은 refresh 토큰은 두 번 쓰지 못한다(두 번째 호출 = 401).
- /auth/logout 은 jti DEL — 이미 없어도 204 (idempotent).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.security import (
    TokenType,
    create_refresh_token,
    decode_token,
    register_refresh_jti,
)
from app.domains.users.models import User


async def _issue_refresh(redis: Redis, user: User) -> tuple[str, str]:
    """테스트용 헬퍼: refresh 토큰 발급 + jti whitelist 등록."""
    token, jti = create_refresh_token(user.id, user.discord_id)
    await register_refresh_jti(redis, jti, user.id)
    return token, jti


@pytest.mark.asyncio
async def test_refresh_rotates_tokens_and_revokes_old_jti(
    client: AsyncClient, redis_client: Redis, user: User
) -> None:
    refresh_token, old_jti = await _issue_refresh(redis_client, user)

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != refresh_token

    # old jti 는 whitelist 에서 사라졌고, new jti 만 남아 있어야 한다.
    assert await redis_client.exists(f"refresh_jti:{old_jti}") == 0
    new_payload = decode_token(body["refresh_token"], TokenType.REFRESH)
    assert await redis_client.exists(f"refresh_jti:{new_payload['jti']}") == 1


@pytest.mark.asyncio
async def test_refresh_rejects_reuse_of_same_token(
    client: AsyncClient, redis_client: Redis, user: User
) -> None:
    refresh_token, _ = await _issue_refresh(redis_client, user)

    first = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert first.status_code == 200

    # 같은 refresh 를 다시 사용 — rotation 으로 jti DEL 됐으므로 401.
    second = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert second.status_code == 401
    assert second.json()["code"] == "INVALID_AUTH_TOKEN"


@pytest.mark.asyncio
async def test_refresh_rejects_expired_token(
    client: AsyncClient, redis_client: Redis, user: User
) -> None:
    # 직접 만료된 JWT 를 만들어 본다. register_refresh_jti 는 일부러 호출 — 만료가 우선.
    settings = get_settings()
    expired_payload = {
        "sub": str(user.id),
        "discord_id": user.discord_id,
        "iat": int((datetime.now(timezone.utc) - timedelta(days=40)).timestamp()),
        "exp": int((datetime.now(timezone.utc) - timedelta(days=10)).timestamp()),
        "jti": "expired-jti",
        "typ": TokenType.REFRESH.value,
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    await register_refresh_jti(redis_client, "expired-jti", user.id)

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": expired_token}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_AUTH_TOKEN"


@pytest.mark.asyncio
async def test_logout_revokes_jti_then_refresh_fails(
    client: AsyncClient, redis_client: Redis, user: User
) -> None:
    refresh_token, jti = await _issue_refresh(redis_client, user)

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh_token}
    )
    assert logout_response.status_code == 204
    assert await redis_client.exists(f"refresh_jti:{jti}") == 0

    # 로그아웃 후 같은 refresh 로 갱신 시도 — whitelist 미존재로 401.
    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json()["code"] == "INVALID_AUTH_TOKEN"


@pytest.mark.asyncio
async def test_logout_is_idempotent(
    client: AsyncClient, redis_client: Redis, user: User
) -> None:
    refresh_token, _ = await _issue_refresh(redis_client, user)

    first = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh_token}
    )
    assert first.status_code == 204

    # 두 번째 호출도 204 — DEL 은 키가 없어도 무해.
    second = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh_token}
    )
    assert second.status_code == 204
