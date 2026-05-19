from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_state_token
from app.domains.users.models import User


@pytest.mark.asyncio
async def test_callback_creates_user_and_redirects_with_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
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
