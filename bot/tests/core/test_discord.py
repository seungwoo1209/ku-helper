"""DiscordBotClient.send_embed 단위 테스트 (§A-1).

실제 Discord 연결 없이 AsyncMock 으로 내부 SDK 호출만 검증한다.
"""

import pytest
import discord
from unittest.mock import AsyncMock, MagicMock

from app.core.discord import DiscordBotClient


@pytest.fixture
def dc_channel() -> AsyncMock:
    channel = AsyncMock(spec=discord.DMChannel)
    return channel


@pytest.fixture
def dc_user(dc_channel: AsyncMock) -> AsyncMock:
    user = AsyncMock(spec=discord.User)
    user.create_dm.return_value = dc_channel
    return user


@pytest.fixture
def dc_raw_client(dc_user: AsyncMock) -> MagicMock:
    client = MagicMock(spec=discord.Client)
    client.fetch_user = AsyncMock(return_value=dc_user)
    return client


@pytest.fixture
def dc_bot_client(dc_raw_client: MagicMock) -> DiscordBotClient:
    settings = MagicMock()
    settings.discord_bot_token.get_secret_value.return_value = "test-token"
    return DiscordBotClient(dc_raw_client, settings)


@pytest.mark.asyncio
async def test_open_dm_channel_calls_fetch_user_and_create_dm(
    dc_bot_client: DiscordBotClient,
    dc_raw_client: MagicMock,
    dc_user: AsyncMock,
    dc_channel: AsyncMock,
) -> None:
    result = await dc_bot_client.open_dm_channel(discord_id=123456)

    dc_raw_client.fetch_user.assert_awaited_once_with(123456)
    dc_user.create_dm.assert_awaited_once()
    assert result is dc_channel


@pytest.mark.asyncio
async def test_send_embed_calls_channel_send(
    dc_bot_client: DiscordBotClient,
    dc_raw_client: MagicMock,
    dc_channel: AsyncMock,
) -> None:
    embed = discord.Embed(title="테스트 임베드")

    await dc_bot_client.send_embed(discord_id=111, embed=embed)

    dc_raw_client.fetch_user.assert_awaited_once_with(111)
    dc_channel.send.assert_awaited_once_with(embed=embed)


@pytest.mark.asyncio
async def test_send_embed_propagates_http_exception(
    dc_bot_client: DiscordBotClient,
    dc_channel: AsyncMock,
) -> None:
    """discord.HTTPException 은 Sender 가 처리하도록 그대로 전파해야 한다."""
    dc_channel.send.side_effect = discord.HTTPException(
        MagicMock(status=403), "Forbidden"
    )
    embed = discord.Embed(title="실패 임베드")

    with pytest.raises(discord.HTTPException):
        await dc_bot_client.send_embed(discord_id=999, embed=embed)
