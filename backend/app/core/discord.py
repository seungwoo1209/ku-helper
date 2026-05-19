import asyncio
from typing import Any

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

    async def send_dm(self, discord_user_id: int, content: str) -> None:
        log = logger.bind(discord_id=discord_user_id, content_length=len(content))
        log.info("discord_dm_send_started")
        try:
            channel_id = await self._create_dm_channel(discord_user_id)
        except DiscordBotApiError:
            log.exception("discord_dm_channel_create_failed")
            raise
        log = log.bind(channel_id=channel_id)
        try:
            await self._post_message(channel_id, content)
        except DiscordBotApiError:
            log.exception("discord_dm_message_post_failed")
            raise
        log.info("discord_dm_send_succeeded")

    async def _create_dm_channel(self, discord_user_id: int) -> str:
        url = f"{_DISCORD_API_BASE}/users/@me/channels"
        body = {"recipient_id": str(discord_user_id)}
        response = await self._request_with_retry("POST", url, body)
        try:
            channel_id = str(response.json()["id"])
        except (KeyError, ValueError) as exc:
            logger.error(
                "discord_dm_channel_response_parse_failed",
                discord_id=discord_user_id,
                status_code=response.status_code,
            )
            raise DiscordBotApiError("Discord DM 채널 응답 파싱 실패.") from exc
        return channel_id

    async def _post_message(self, channel_id: str, content: str) -> None:
        url = f"{_DISCORD_API_BASE}/channels/{channel_id}/messages"
        body = {"content": content}
        await self._request_with_retry("POST", url, body)

    async def _request_with_retry(
        self, method: str, url: str, body: dict[str, str]
    ) -> httpx.Response:
        for attempt in range(_MAX_RATE_LIMIT_RETRIES):
            response = await self._client.request(
                method, url, json=body, headers=self._bot_headers
            )
            elapsed_ms = round(response.elapsed.total_seconds() * 1000, 1)
            if 200 <= response.status_code < 300:
                logger.debug(
                    "discord_bot_api_ok",
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    elapsed_ms=elapsed_ms,
                    attempt=attempt,
                )
                return response
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "1"))
                logger.warning(
                    "discord_bot_rate_limited",
                    method=method,
                    url=url,
                    attempt=attempt,
                    retry_after=retry_after,
                    elapsed_ms=elapsed_ms,
                )
                await asyncio.sleep(retry_after)
                continue
            error_code, error_message = _extract_discord_error(response)
            logger.error(
                "discord_bot_api_error",
                method=method,
                url=url,
                status_code=response.status_code,
                discord_error_code=error_code,
                discord_error_message=error_message,
                elapsed_ms=elapsed_ms,
                attempt=attempt,
            )
            raise DiscordBotApiError(
                f"Discord 봇 API 오류 (status={response.status_code},"
                f" discord_code={error_code})."
            )

        logger.error(
            "discord_bot_rate_limit_exceeded",
            method=method,
            url=url,
            max_retries=_MAX_RATE_LIMIT_RETRIES,
        )
        raise DiscordBotApiError("Discord 봇 API rate limit 재시도 초과.")


def _extract_discord_error(response: httpx.Response) -> tuple[int | None, str | None]:
    # Discord 에러 응답 포맷: {"code": <int>, "message": "<str>", ...}
    try:
        payload: Any = response.json()
    except ValueError:
        return None, None
    if not isinstance(payload, dict):
        return None, None
    code = payload.get("code")
    message = payload.get("message")
    return (
        code if isinstance(code, int) else None,
        message if isinstance(message, str) else None,
    )
