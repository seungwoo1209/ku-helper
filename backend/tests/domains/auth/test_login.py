from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from app.core.security import TokenType, decode_token


@pytest.mark.asyncio
async def test_login_redirects_to_discord(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/discord/login", follow_redirects=False)
    assert response.status_code == 307
    assert "discord.com" in response.headers["location"]


@pytest.mark.asyncio
async def test_login_state_token_is_valid_jwt(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/discord/login", follow_redirects=False)
    qs = parse_qs(urlparse(response.headers["location"]).query)
    state = qs["state"][0]
    # state JWT가 우리가 발급한 토큰이며 type=state여야 한다.
    payload = decode_token(state, TokenType.STATE)
    assert payload["typ"] == "state"


@pytest.mark.asyncio
async def test_login_integration_type_is_user_install(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/auth/discord/login", follow_redirects=False)
    qs = parse_qs(urlparse(response.headers["location"]).query)
    assert qs["integration_type"][0] == "1"
