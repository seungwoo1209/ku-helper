from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, create_state_token, decode_token
from app.domains.users.models import User


@pytest.mark.asyncio
async def test_callback_creates_user_and_redirects_with_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    discord_oauth_mocks,
) -> None:
    state = create_state_token()
    response = await client.get(
        "/api/v1/auth/discord/callback",
        params={"code": "fake-code", "state": state},
    )
    assert response.status_code == 307
    location = response.headers["location"]
    query = parse_qs(urlparse(location).query)
    assert "access_token" in query and "refresh_token" in query
    assert query["access_token"][0]
    assert query["refresh_token"][0]

    stored = (
        await db_session.execute(
            select(User).where(User.discord_id == 987654321098765432)
        )
    ).scalar_one()
    assert stored.discord_username == "discordian"

    # 발급된 refresh jti 가 Redis whitelist 에 등록돼야 한다(F-05 갱신 가능 상태).
    refresh_payload = decode_token(query["refresh_token"][0], TokenType.REFRESH)
    assert await redis_client.exists(f"refresh_jti:{refresh_payload['jti']}") == 1


@pytest.mark.asyncio
async def test_callback_rejects_invalid_state(
    client: AsyncClient,
    discord_oauth_mocks,
) -> None:
    response = await client.get(
        "/api/v1/auth/discord/callback",
        params={"code": "fake-code", "state": "not-a-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_OAUTH_STATE"


@pytest.mark.asyncio
async def test_callback_rejects_state_replay(
    client: AsyncClient,
    redis_client: Redis,
    discord_oauth_mocks,
) -> None:
    """같은 state 로 두 번째 콜백이 들어오면 401. Discord 토큰 교환이 두 번째에 일어나지
    않는다(replay 가 외부 호출까지 새지 않음을 회귀 가드)."""
    state = create_state_token()
    state_payload = decode_token(state, TokenType.STATE)

    first = await client.get(
        "/api/v1/auth/discord/callback",
        params={"code": "fake-code", "state": state},
    )
    assert first.status_code == 307
    assert (
        await redis_client.exists(f"state_used:{state_payload['jti']}") == 1
    )
    first_external_calls = discord_oauth_mocks.calls.call_count

    second = await client.get(
        "/api/v1/auth/discord/callback",
        params={"code": "fake-code", "state": state},
    )
    assert second.status_code == 401
    assert second.json()["code"] == "INVALID_OAUTH_STATE"
    # 두 번째 호출은 Redis SET NX 단계에서 차단 — Discord 외부 호출이 추가로 일어나지 않는다.
    assert discord_oauth_mocks.calls.call_count == first_external_calls
