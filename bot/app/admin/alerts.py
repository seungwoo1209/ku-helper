"""F-22 크롤러 실패 → 관리자 DM 알림 (architecture.md §Admin).

크롤러 4종(subway/lunch/restaurants/library) 중 어느 하나가 실패하면
즉시 Sender 큐를 통해 관리자에게 DM을 보낸다(single-trigger, 카운터/쿨다운 없음).
노이즈 가드(임계값·윈도우·쿨다운)는 roadmap §E 후속 PR에서 재도입한다.
"""

from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING

import discord
import structlog

from app.core.config import Settings
from app.notifications.sender import SendDmTask

if TYPE_CHECKING:
    import asyncio

_logger = structlog.get_logger(__name__)

# 임베드 색상 (빨강)
_COLOR_RED = 0xE74C3C
# 오류 요약 최대 길이
_ERROR_EXCERPT_MAX = 200


class CrawlerSource(StrEnum):
    SUBWAY = "subway"
    LUNCH = "lunch"
    RESTAURANTS = "restaurants"
    LIBRARY = "library"


def build_admin_failure_embed(
    source: CrawlerSource,
    error_message: str,
    occurred_at: datetime,
) -> discord.Embed:
    """관리자 알림용 임베드를 생성한다.

    discord.Embed 직접 인스턴스화는 이 모듈(admin/alerts.py)에서만 허용.
    architecture.md §Admin 과 code_style.md §discord.Embed 직접 인스턴스화 규칙 참고.
    """
    from zoneinfo import ZoneInfo

    kst = ZoneInfo("Asia/Seoul")
    occurred_kst = occurred_at.astimezone(kst)
    occurred_str = occurred_kst.strftime("%Y-%m-%d %H:%M:%S KST")

    excerpt = error_message[:_ERROR_EXCERPT_MAX]

    embed = discord.Embed(
        title=f"🚨 크롤러 실패: {source}",
        color=_COLOR_RED,
    )
    embed.add_field(name="오류 요약", value=excerpt or "(없음)", inline=False)
    embed.add_field(name="발생 시각 KST", value=occurred_str, inline=False)
    return embed


async def enqueue_admin_alerts(
    queue: "asyncio.Queue[SendDmTask]",
    settings: Settings,
    source: CrawlerSource,
    exc: BaseException,
) -> None:
    """크롤러 실패 발생 즉시 관리자에게 알림을 큐에 적재한다.

    admin_discord_ids 가 비어 있으면 warn 로그 후 noop.
    이 함수 자체의 예외는 swallow — 워커 루프를 멈추지 않아야 한다.
    """
    try:
        admin_ids = settings.admin_discord_ids
        if not admin_ids:
            _logger.warning("admin_alert_no_recipients", source=source)
            return

        occurred_at = datetime.now(tz=timezone.utc)
        error_message = str(exc)[:_ERROR_EXCERPT_MAX]
        embed = build_admin_failure_embed(source, error_message, occurred_at)
        payload: dict[str, object] = {
            "source": source.value,
            "code": exc.__class__.__name__,
            "error_excerpt": error_message,
        }

        for discord_id in admin_ids:
            task = SendDmTask(
                notification_id=None,
                user_id=discord_id,
                discord_id=discord_id,
                embed=embed,
                payload=payload,
                immediate_send_request_id=None,
            )
            await queue.put(task)
            _logger.info(
                "admin_alert_enqueued",
                source=source,
                discord_id=discord_id,
            )
    except Exception:
        _logger.exception("admin_alert_enqueue_failed", source=source)
