"""F-22 크롤러 실패 → 관리자 DM 알림 (architecture.md §Admin).

크롤러 4종(subway/lunch/restaurants/library) 중 어느 하나가
5분 윈도우 안에 _FAIL_THRESHOLD 회 연속 실패하면 Sender 큐를 통해 관리자에게 DM.
동일 source 30분 쿨다운으로 중복 알림 차단.
"""

from collections.abc import Awaitable
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, cast

import discord
import structlog

from app.core.config import Settings
from app.notifications.sender import SendDmTask

if TYPE_CHECKING:
    import asyncio

    from redis.asyncio import Redis

_logger = structlog.get_logger(__name__)

# 5분 윈도우 — 이 TTL 안에 _FAIL_THRESHOLD 회 연속 실패해야 알림 발송.
_FAIL_COUNTER_TTL_SECONDS = 300
# 동일 source 중복 DM 차단 쿨다운 — 30분.
_COOLDOWN_TTL_SECONDS = 1800
_FAIL_THRESHOLD = 3

# 임베드 색상 (빨강)
_COLOR_RED = 0xE74C3C
# 오류 요약 최대 길이
_ERROR_EXCERPT_MAX = 200


class CrawlerSource(StrEnum):
    SUBWAY = "subway"
    LUNCH = "lunch"
    RESTAURANTS = "restaurants"
    LIBRARY = "library"


async def increment_crawler_failure(redis: "Redis", source: CrawlerSource) -> int:
    """Redis `crawler_fail:{source}` 카운터를 1 증가시키고 현재 값을 반환.

    첫 번째 INCR(값 == 1)일 때만 EXPIRE 를 설정한다.
    이후 INCR 은 TTL 을 건드리지 않아 5분 윈도우가 유지된다.
    """
    key = f"crawler_fail:{source}"
    count = await cast("Awaitable[int]", redis.incr(key))
    if count == 1:
        await cast("Awaitable[object]", redis.expire(key, _FAIL_COUNTER_TTL_SECONDS))
    return count


async def mark_alert_cooldown(redis: "Redis", source: CrawlerSource) -> bool:
    """쿨다운 키를 NX 방식으로 설정. 성공(키 없었음) 시 True 반환.

    True == 알림을 보낼 자격 있음.
    False == 이미 30분 쿨다운 중이므로 skip.
    """
    key = f"crawler_alert_cooldown:{source}"
    result = await cast(
        "Awaitable[bool | None]",
        redis.set(key, "1", nx=True, ex=_COOLDOWN_TTL_SECONDS),
    )
    # redis-py: SET NX 성공 시 True, 실패(키 이미 존재) 시 None.
    return result is True


def build_admin_failure_embed(
    source: CrawlerSource,
    error_message: str,
    count: int,
    occurred_at: datetime,
) -> discord.Embed:
    """관리자 알림용 임베드를 생성한다.

    discord.Embed 직접 인스턴스화는 이 모듈(admin/alerts.py)에서만 허용.
    architecture.md §Admin 과 code_style.md §discord.Embed 직접 인스턴스화 규칙 참고.
    """
    # occurred_at 을 KST 로 표시.
    from zoneinfo import ZoneInfo

    kst = ZoneInfo("Asia/Seoul")
    occurred_kst = occurred_at.astimezone(kst)
    occurred_str = occurred_kst.strftime("%Y-%m-%d %H:%M:%S KST")

    excerpt = error_message[:_ERROR_EXCERPT_MAX]

    embed = discord.Embed(
        title=f"🚨 크롤러 실패: {source}",
        color=_COLOR_RED,
    )
    embed.add_field(name="횟수", value=str(count), inline=True)
    embed.add_field(name="오류 요약", value=excerpt or "(없음)", inline=False)
    embed.add_field(name="발생 시각 KST", value=occurred_str, inline=False)
    return embed


async def maybe_enqueue_admin_alerts(
    queue: "asyncio.Queue[SendDmTask]",
    redis: "Redis",
    settings: Settings,
    source: CrawlerSource,
    exc: BaseException,
) -> None:
    """크롤러 실패 카운터를 증가시키고, 임계값 초과 시 관리자에게 알림을 큐에 적재한다.

    - 카운터 < _FAIL_THRESHOLD: 아무 작업 없음.
    - 카운터 >= _FAIL_THRESHOLD AND 쿨다운 NX 성공: 모든 admin 에게 SendDmTask 적재.
    - 쿨다운 중(NX 실패): skip.
    - swallow 유지 — 이 함수 자체의 예외가 워커 루프를 멈추지 않도록 내부에서 처리.
    """
    try:
        count = await increment_crawler_failure(redis, source)
        _logger.info(
            "crawler_failure_counted",
            source=source,
            count=count,
            threshold=_FAIL_THRESHOLD,
        )

        if count < _FAIL_THRESHOLD:
            return

        can_alert = await mark_alert_cooldown(redis, source)
        if not can_alert:
            _logger.debug(
                "crawler_alert_cooldown_active",
                source=source,
                count=count,
            )
            return

        occurred_at = datetime.now(tz=timezone.utc)
        error_message = str(exc)[:_ERROR_EXCERPT_MAX]
        embed = build_admin_failure_embed(source, error_message, count, occurred_at)
        payload: dict[str, object] = {
            "source": source.value,
            "code": exc.__class__.__name__,
            "count": count,
            "error_excerpt": error_message,
        }

        admin_ids = settings.admin_discord_ids
        if not admin_ids:
            _logger.warning("admin_alert_no_recipients", source=source)
            return

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
                count=count,
            )
    except Exception:
        _logger.exception("admin_alert_enqueue_failed", source=source)
