import discord

from app.core.config import Settings


class DiscordBotClient:
    """discord.py Client를 감싸는 단일 진입점.

    봇 토큰은 이 클래스 외부로 노출되지 않는다 (`get_secret_value()` 호출은 start() 안에서만).
    send_embed는 §A-1에서 구현한다.
    """

    def __init__(self, dc_client: discord.Client, settings: Settings) -> None:
        self._client = dc_client
        self._settings = settings

    async def start(self) -> None:
        await self._client.start(self._settings.discord_bot_token.get_secret_value())

    async def close(self) -> None:
        await self._client.close()

    async def send_embed(self, discord_id: int, embed: discord.Embed) -> None:
        raise NotImplementedError("§A-1에서 구현")
