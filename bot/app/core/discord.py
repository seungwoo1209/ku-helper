import discord

from app.core.config import Settings


class DiscordBotClient:
    """discord.py Client를 감싸는 단일 진입점.

    봇 토큰은 이 클래스 외부로 노출되지 않는다 (`get_secret_value()` 호출은 start() 안에서만).
    Discord API 429 처리는 discord.py 내장 rate-limit 핸들러에 위임한다.
    §A-3 지수 백오프 재시도는 다음 PR.
    """

    def __init__(self, dc_client: discord.Client, settings: Settings) -> None:
        self._client = dc_client
        self._settings = settings

    async def start(self) -> None:
        await self._client.start(self._settings.discord_bot_token.get_secret_value())

    async def close(self) -> None:
        await self._client.close()

    async def wait_until_ready(self) -> None:
        await self._client.wait_until_ready()

    async def open_dm_channel(self, discord_id: int) -> discord.DMChannel:
        """discord_id 에 해당하는 DM 채널을 열고 반환한다.

        매 호출마다 fetch_user + create_dm 을 수행한다.
        채널 캐시는 부하 측정 후 별도 PR(§A-1 주석 참고).
        discord.HTTPException 은 그대로 전파한다 — Sender 가 catch 해 FAILED INSERT.
        """
        dc_user = await self._client.fetch_user(discord_id)
        dc_channel = await dc_user.create_dm()
        return dc_channel

    async def send_embed(self, discord_id: int, embed: discord.Embed) -> None:
        """discord_id 사용자에게 embed DM을 전송한다.

        discord.HTTPException 은 그대로 전파한다.
        """
        dc_channel = await self.open_dm_channel(discord_id)
        await dc_channel.send(embed=embed)
