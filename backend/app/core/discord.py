import asyncio

import httpx
import structlog

from app.core.config import Settings
from app.core.exceptions import AppException


_DISCORD_API_BASE = "https://discord.com/api/v10"
_MAX_RATE_LIMIT_RETRIES = 3
logger = structlog.get_logger(__name__)


class DiscordBotApiError(AppException):
    code = "DISCORD_BOT_API_ERROR"
    detail = "Discord 봇 API 호출에 실패했습니다."
    status_code = 502


class DiscordBotClient:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = http_client
        self._settings = settings

    @property
    def _bot_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self._settings.discord_bot_token.get_secret_value()}",
        }

    async def add_guild_member(
        self, discord_user_id: int, user_access_token: str
    ) -> None:
        # PUT /guilds/{guild_id}/members/{user_id}
        # 응답: 201 = 가입, 204 = 이미 가입됨. 둘 다 성공.
        url = (
            f"{_DISCORD_API_BASE}/guilds/{self._settings.discord_guild_id}"
            f"/members/{discord_user_id}"
        )
        body = {"access_token": user_access_token}

        for attempt in range(_MAX_RATE_LIMIT_RETRIES):
            response = await self._client.put(url, json=body, headers=self._bot_headers)
            if response.status_code in (200, 201, 204):
                return
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "1"))
                logger.warning(
                    "discord_bot_rate_limited",
                    attempt=attempt,
                    retry_after=retry_after,
                )
                await asyncio.sleep(retry_after)
                continue
            raise DiscordBotApiError(
                f"Discord 봇 API 오류 (status={response.status_code})."
            )

        raise DiscordBotApiError("Discord 봇 API rate limit 재시도 초과.")
