import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_state_token
from app.domains.users.models import User


@pytest.mark.asyncio
async def test_callback_creates_user_and_returns_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
    discord_oauth_mocks,
) -> None:
    state = create_state_token()
    response = await client.get(
        "/api/v1/auth/discord/callback",
        params={"code": "fake-code", "state": state},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body and "refresh_token" in body

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
