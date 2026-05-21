"""LIBRARY 알림 워커 — F-13 임계값 알림 + F-14 상태 기반 중복 방지 + F-15 긴급.

Scheduler → Worker → (LibraryClient · Repository · Redis) → Sender 순서.

F-14 상태머신: Redis 키 `library_alert:{user_id}:{room_id}` ∈ {above, below}.
직전 above & 현재 임계값 이하 → 발송 후 below. 회복(임계값 위) 시 above. 시간 쿨다운이
아니라 상태 전이 기반이라, 회복 없이 계속 임계값 이하면 재발송하지 않는다.
"""

from collections.abc import Awaitable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

import structlog

from app.admin.alerts import CrawlerSource, maybe_enqueue_admin_alerts
from app.core.exceptions import BotException
from app.crawlers.library.client import LibraryClient
from app.crawlers.library.exceptions import LibraryCrawlerFailed
from app.db.models import NotificationDeliveryStatus, NotificationType
from app.notifications.history_repository import NotificationHistoryRepository
from app.notifications.library.embeds import (
    build_library_embed,
    build_library_immediate_embed,
)
from app.notifications.lunch.repository import ImmediateSendRequestRepository
from app.notifications.repository import NotificationRepository
from app.notifications.sender import SendDmTask
from app.scheduler.context import JobContext

if TYPE_CHECKING:
    from redis.asyncio import Redis

_logger = structlog.get_logger(__name__)

_STATE_ABOVE = "above"
_STATE_BELOW = "below"
# F-14 상태 키 TTL(초). 시간 리셋이 아니라 상태머신이라 충분히 길게 둔다(24h).
_STATE_TTL_SECONDS = 86400
# 즉시 발송 폴링 시 한 틱에 픽업할 최대 row 수.
_POLL_LIMIT = 50


def _state_key(user_id: int, room_id: int) -> str:
    return f"library_alert:{user_id}:{room_id}"


async def _get_state(redis: "Redis", key: str) -> str | None:
    # redis-py async 메서드는 sync/async overload라 mypy가 union을 본다(core/redis.py 참고).
    # decode_responses=True 환경이므로 실제 반환은 str | None.
    return await cast("Awaitable[str | None]", redis.get(key))


async def _set_state(redis: "Redis", key: str, value: str) -> None:
    await cast("Awaitable[object]", redis.set(key, value, ex=_STATE_TTL_SECONDS))


async def run_library_job(ctx: JobContext) -> None:
    """LIBRARY 활성 구독을 폴링하여 F-13/F-14/F-15 조건 충족 시 Sender 큐에 적재한다."""
    redis = ctx.redis_client
    now = datetime.now(tz=timezone.utc)

    try:
        client = LibraryClient(ctx.http_client, ctx.settings, redis=ctx.redis_client)

        async with ctx.session_maker() as session:
            repo = NotificationRepository(session)
            subs = await repo.list_active_subscriptions_with_user(
                NotificationType.LIBRARY
            )
        _logger.info("library_poll_tick", count=len(subs))
        if not subs:
            return

        snapshot = await client.fetch_seats()

        for notification, user in subs:
            cfg = notification.config
            try:
                room_id = int(cfg["reading_room_id"])
                threshold = int(cfg["threshold"])
            except (KeyError, TypeError, ValueError):
                _logger.warning(
                    "library_skip_invalid_config", notification_id=notification.id
                )
                continue
            urgent_threshold = _coerce_optional_int(cfg.get("urgent_threshold"))

            room = snapshot.get(room_id)
            if room is None:
                _logger.debug(
                    "library_skip_room_absent",
                    notification_id=notification.id,
                    room_id=room_id,
                )
                continue

            current = _STATE_BELOW if room.available <= threshold else _STATE_ABOVE
            key = _state_key(user.id, room_id)
            stored = await _get_state(redis, key)
            # 키 미존재 시 above 로 간주 — 설정 직후 이미 임계값 이하면 1회 발송.
            prev_state = stored if stored is not None else _STATE_ABOVE

            if current == _STATE_BELOW:
                if prev_state == _STATE_ABOVE:
                    embed, payload = build_library_embed(
                        room, threshold, urgent_threshold, now
                    )
                    await ctx.queue.put(
                        SendDmTask(
                            notification_id=notification.id,
                            user_id=user.id,
                            discord_id=user.discord_id,
                            embed=embed,
                            payload=payload,
                        )
                    )
                    # 발송=큐 적재 시점에 below 갱신. F-14(중복방지)가 전달 정확성보다 우선.
                    await _set_state(redis, key, _STATE_BELOW)
                    _logger.info(
                        "library_queued",
                        notification_id=notification.id,
                        user_id=user.id,
                        room_id=room_id,
                        available=room.available,
                        threshold=threshold,
                        is_urgent=payload["is_urgent"],
                    )
                # prev below: 회복 전까지 재발송 안 함.
            elif prev_state != _STATE_ABOVE:
                # current above 인데 직전이 below — 회복. 상태만 above 로 갱신.
                await _set_state(redis, key, _STATE_ABOVE)
                _logger.debug(
                    "library_recovered",
                    notification_id=notification.id,
                    room_id=room_id,
                )
    except (LibraryCrawlerFailed, BotException) as exc:
        # crawler/도메인 예외는 swallow + 로그. 다음 틱 재시도.
        _logger.warning("library_poll_failed", code=exc.code)
        await maybe_enqueue_admin_alerts(
            ctx.queue, ctx.redis_client, ctx.settings, CrawlerSource.LIBRARY, exc
        )


async def run_immediate_send_library_job(ctx: JobContext) -> None:
    """immediate_send_requests (type=LIBRARY) 폴링 → 현재 좌석 조회 → Sender 큐 적재.

    아키텍처 예외: crawler 실패·열람실 부재 시 워커가 직접 NotificationHistoryRepository
    .insert_result(status=FAILED) 를 호출한다. embed/payload 가 없어 SendDmTask 를 만들 수
    없으면 history row 없이 LEFT JOIN 가드가 풀리지 않아 매 틱 재시도되기 때문(lunch/transit
    즉시 발송과 동일). Redis 는 쓰지 않는다 — 즉시 발송엔 상태머신이 없다.
    """
    now = datetime.now(tz=timezone.utc)

    try:
        client = LibraryClient(ctx.http_client, ctx.settings, redis=ctx.redis_client)

        async with ctx.session_maker() as session:
            repo = ImmediateSendRequestRepository(session)
            rows = await repo.list_pending(NotificationType.LIBRARY, limit=_POLL_LIMIT)

        if not rows:
            return
        _logger.info("immediate_send_library_tick", count=len(rows))

        for row in rows:
            if row.id in ctx.immediate_send_inflight:
                continue
            ctx.immediate_send_inflight.add(row.id)

            room_id = _coerce_optional_int(row.payload.get("reading_room_id"))

            try:
                snapshot = await client.fetch_seats()
            except (LibraryCrawlerFailed, BotException) as exc:
                await _insert_immediate_failure(ctx, row.id, row.user_id, exc.code)
                ctx.immediate_send_inflight.discard(row.id)
                continue

            room = snapshot.get(room_id) if room_id is not None else None
            if room is None:
                await _insert_immediate_failure(ctx, row.id, row.user_id, "room_absent")
                ctx.immediate_send_inflight.discard(row.id)
                continue

            embed, payload = build_library_immediate_embed(room, now)
            await ctx.queue.put(
                SendDmTask(
                    notification_id=None,
                    user_id=row.user_id,
                    discord_id=row.discord_id,
                    embed=embed,
                    payload=payload,
                    immediate_send_request_id=row.id,
                )
            )
            _logger.info(
                "immediate_send_library_queued",
                request_id=row.id,
                user_id=row.user_id,
                room_id=room_id,
            )
    except BotException as exc:
        _logger.exception("immediate_send_library_failed", code=exc.code)


async def _insert_immediate_failure(
    ctx: JobContext, request_id: int, user_id: int, reason: str
) -> None:
    async with ctx.session_maker() as session:
        history = NotificationHistoryRepository(session)
        await history.insert_result(
            notification_id=None,
            immediate_send_request_id=request_id,
            user_id=user_id,
            status=NotificationDeliveryStatus.FAILED,
            payload={"reason": reason},
            failure_reason=reason[:200],
        )
        await session.commit()


def _coerce_optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
