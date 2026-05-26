import asyncio
import random
from collections.abc import Awaitable
from datetime import datetime, timedelta, timezone
from datetime import time as datetime_time
from typing import cast
from zoneinfo import ZoneInfo

import structlog

from app.admin.alerts import CrawlerSource, enqueue_admin_alerts
from app.core.exceptions import BotException
from app.crawlers.lunch.exceptions import LunchCrawlerFailed
from app.crawlers.restaurants.exceptions import RestaurantsCrawlerFailed
from app.db.models import NotificationDeliveryStatus, NotificationType
from app.notifications.history_repository import NotificationHistoryRepository
from app.notifications.lunch.embeds import (
    build_lunch_immediate_embed,
    build_lunch_scheduled_embed,
)
from app.notifications.lunch.repository import ImmediateSendRequestRepository
from app.notifications.repository import NotificationRepository
from app.notifications.sender import SendDmTask
from app.scheduler.context import JobContext

_logger = structlog.get_logger(__name__)

_RESTAURANTS_SAMPLE_SIZE = 3
_POLL_LIMIT = 50

# KST 타임존 — 윈도우 비교와 dedup 키 날짜 계산에 사용한다.
_KST = ZoneInfo("Asia/Seoul")

# 정시 윈도우 허용 범위(초). 60초 폴링 granularity + 재기동 jitter 흡수용.
_NOTIFY_AT_GRACE_SECONDS = 180

# dedup Redis 키 TTL(초). 25h — 하루 1회 발송 보장 + 자정 즈음 TTL 만료 방지 여유.
_DEDUP_TTL_SECONDS = 90000


def _parse_notify_at(raw: str | None) -> datetime_time | None:
    """config JSONB 의 'HH:MM:SS' 또는 'HH:MM' 문자열 → datetime.time.

    Pydantic time 직렬화는 HH:MM:SS, 수동 INSERT 시 HH:MM 도 허용한다.
    파싱 실패 시 None 반환 — 호출자가 skip 처리한다.
    """
    if raw is None:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None


async def run_lunch_job(ctx: JobContext) -> None:
    """정기 LUNCH 구독을 폴링하여 notify_at 정시 윈도우 조건 충족 시 Sender 큐에 적재한다.

    흐름:
    1. 활성 LUNCH 구독 목록 조회 (User JOIN 포함).
    2. 각 구독마다 notify_at 정시 윈도우 + Redis dedup 검사.
    3. 조건 충족 시 LunchClient + RestaurantsClient 호출 → 임베드 빌드 → 큐 적재.
    4. 크롤러 실패는 구독별로 격리하고 틱당 1회 admin alert.

    ctx.redis_client 가 None 이면 잡 skip(Redis 없이 dedup 불가).
    ctx.lunch_client / ctx.restaurants_client 가 None 이면 잡 skip.
    """
    lunch_client = ctx.lunch_client
    restaurants_client = ctx.restaurants_client
    if lunch_client is None or restaurants_client is None:
        return

    redis = ctx.redis_client

    now = datetime.now(tz=timezone.utc)
    now_kst = now.astimezone(_KST)
    kst_date = now_kst.date().isoformat()

    # 틱 내 크롤러 실패 여부를 추적해 admin alert 를 틱당 1회만 발송한다.
    _last_crawler_exc: BaseException | None = None
    _last_crawler_source: CrawlerSource | None = None

    try:
        async with ctx.session_maker() as session:
            repo = NotificationRepository(session)
            subs = await repo.list_active_subscriptions_with_user(
                NotificationType.LUNCH
            )
        _logger.info("lunch_poll_tick", count=len(subs))

        for notification, user in subs:
            cfg = notification.config

            # 1. notify_at 파싱.
            notify_at = _parse_notify_at(cfg.get("notify_at"))
            if notify_at is None:
                _logger.warning(
                    "lunch_skip_invalid_notify_at",
                    notification_id=notification.id,
                    raw_notify_at=cfg.get("notify_at"),
                )
                continue

            # 2. 정시 윈도우 검사 — aware datetime 으로 변환해 비교.
            notify_at_dt = datetime(
                now_kst.year,
                now_kst.month,
                now_kst.day,
                notify_at.hour,
                notify_at.minute,
                notify_at.second,
                tzinfo=_KST,
            )
            grace_end_dt = notify_at_dt + timedelta(seconds=_NOTIFY_AT_GRACE_SECONDS)

            if now_kst < notify_at_dt:
                # 아직 발송 시각 전 — skip.
                _logger.debug(
                    "lunch_skip_before_notify_at",
                    notification_id=notification.id,
                    now_kst=now_kst.isoformat(),
                    notify_at=notify_at.isoformat(),
                )
                continue

            if now_kst >= grace_end_dt:
                # 윈도우 지남(지각) — dedup 키 SET 하지 않고 skip.
                _logger.debug(
                    "lunch_skip_after_grace",
                    notification_id=notification.id,
                    now_kst=now_kst.isoformat(),
                    notify_at=notify_at.isoformat(),
                )
                continue

            # 3. 하루 1회 dedup 검사.
            dedup_key = f"lunch_sent:{notification.id}:{kst_date}"
            existing = await cast(
                "Awaitable[object]",
                redis.get(dedup_key),
            )
            if existing is not None:
                _logger.debug(
                    "lunch_skip_already_sent_today",
                    notification_id=notification.id,
                    kst_date=kst_date,
                )
                continue

            # 4. 크롤러 호출 — 구독별 try/except 로 격리.
            try:
                menu, pool = await asyncio.gather(
                    lunch_client.fetch_today_menu(),
                    restaurants_client.fetch_pool(),
                )
            except (LunchCrawlerFailed, RestaurantsCrawlerFailed) as exc:
                # 크롤러 실패 — dedup 키 SET 하지 않아 윈도우 안에서 다음 틱 재시도 가능.
                source = (
                    CrawlerSource.LUNCH
                    if isinstance(exc, LunchCrawlerFailed)
                    else CrawlerSource.RESTAURANTS
                )
                _logger.warning(
                    "lunch_crawler_failed",
                    notification_id=notification.id,
                    source=source,
                    reason=str(exc)[:200],
                )
                _last_crawler_exc = exc
                _last_crawler_source = source
                continue

            # 5. 추천 맛집 샘플.
            recommend_count = int(cfg.get("recommend_count", _RESTAURANTS_SAMPLE_SIZE))
            sampled = (
                tuple(random.sample(pool, min(recommend_count, len(pool))))
                if pool
                else ()
            )

            # 6. 임베드 빌드.
            highlight = bool(cfg.get("highlight_today_pick", True))
            embed = build_lunch_scheduled_embed(menu, sampled, highlight=highlight)

            # 7. payload.
            payload = {
                "cafeteria_name": menu.cafeteria_name,
                "date": menu.date_str,
                "weekday": menu.weekday,
                "corners": [
                    {
                        "name": c.name,
                        "time": c.time,
                        "meal": c.meal,
                        "menus": list(c.menus),
                    }
                    for c in menu.corners
                ],
                "restaurants": [
                    {
                        "name": r.name,
                        "category": r.category,
                        "address": r.address,
                        "link": r.link,
                    }
                    for r in sampled
                ],
            }

            # 8. Sender 큐 적재 + dedup 키 SET.
            await ctx.queue.put(
                SendDmTask(
                    notification_id=notification.id,
                    user_id=user.id,
                    discord_id=user.discord_id,
                    embed=embed,
                    payload=payload,
                )
            )
            await cast(
                "Awaitable[object]",
                redis.set(dedup_key, "1", ex=_DEDUP_TTL_SECONDS),
            )
            _logger.info(
                "lunch_queued",
                notification_id=notification.id,
                user_id=user.id,
            )

        # 루프 종료 후 크롤러 실패가 있었으면 틱당 1회만 admin alert.
        if _last_crawler_exc is not None and _last_crawler_source is not None:
            await enqueue_admin_alerts(
                ctx.queue, ctx.settings, _last_crawler_source, _last_crawler_exc
            )

    except BotException as exc:
        _logger.exception("lunch_poll_failed", code=exc.code)


async def run_immediate_send_lunch_job(ctx: JobContext) -> None:
    """immediate_send_requests (type=LUNCH) 폴링 → 학식·맛집 조회 → Sender 큐 적재.

    중복 적재는 ctx.immediate_send_inflight set 으로 방지. Sender 가 history INSERT 한 뒤
    finally 에서 discard. 봇 재기동 시에는 메모리 set 이 비고 history join 가드만으로 보호.
    """
    lunch_client = ctx.lunch_client
    restaurants_client = ctx.restaurants_client
    if lunch_client is None or restaurants_client is None:
        # 두 client 중 하나라도 lifespan 에서 만들지 못한 환경 — 잡 skip.
        return

    try:
        async with ctx.session_maker() as session:
            repo = ImmediateSendRequestRepository(session)
            rows = await repo.list_pending(NotificationType.LUNCH, limit=_POLL_LIMIT)

        if not rows:
            return
        _logger.info("immediate_send_lunch_tick", count=len(rows))

        for row in rows:
            if row.id in ctx.immediate_send_inflight:
                continue
            ctx.immediate_send_inflight.add(row.id)
            try:
                menu, pool = await asyncio.gather(
                    lunch_client.fetch_today_menu(),
                    restaurants_client.fetch_pool(),
                )
            except (LunchCrawlerFailed, RestaurantsCrawlerFailed) as exc:
                # ARCHITECTURE EXCEPTION: 워커가 직접 notification_history 에 INSERT.
                # bot/CLAUDE.md rule 5 + architecture.md Worker 절은 "Sender 만 INSERT"
                # 를 명시하지만, 크롤러가 실패해 embed/payload 를 만들지 못하는 경우
                # Sender 큐에 넣을 task 자체가 없다. 그래도 history row 가 없으면
                # ImmediateSendRequestRepository.list_pending 의 LEFT JOIN 가드가
                # 풀리지 않아 같은 row 가 매 5초 틱마다 재시도된다. 직접 INSERT 외에
                # 깔끔한 해결책이 없어 이 한 분기에서만 규칙을 우회.
                # 정식 정리는 bot/.claude/roadmap.md 알려진 부채에 명시 —
                # SendDmTask 에 "이미 실패" 플래그를 두고 Sender 가 INSERT 만 수행하는
                # 패턴으로 통합 예정.
                reason = getattr(exc, "reason", str(exc))
                _logger.warning(
                    "immediate_send_lunch_fetch_failed",
                    request_id=row.id,
                    user_id=row.user_id,
                    reason=reason,
                )
                async with ctx.session_maker() as session:
                    history = NotificationHistoryRepository(session)
                    await history.insert_result(
                        notification_id=None,
                        immediate_send_request_id=row.id,
                        user_id=row.user_id,
                        status=NotificationDeliveryStatus.FAILED,
                        payload={"reason": reason},
                        failure_reason=reason[:200],
                    )
                    await session.commit()
                # in-flight 에서 즉시 빼서 같은 row 가 다음 틱에 재시도되지 않도록.
                ctx.immediate_send_inflight.discard(row.id)
                # F-22: 크롤러 종류별로 관리자 카운터 INCR.
                source = (
                    CrawlerSource.LUNCH
                    if isinstance(exc, LunchCrawlerFailed)
                    else CrawlerSource.RESTAURANTS
                )
                await enqueue_admin_alerts(ctx.queue, ctx.settings, source, exc)
                continue

            sampled = (
                tuple(random.sample(pool, k=min(_RESTAURANTS_SAMPLE_SIZE, len(pool))))
                if pool
                else ()
            )
            embed = build_lunch_immediate_embed(menu, sampled)
            payload = {
                "cafeteria_name": menu.cafeteria_name,
                "date": menu.date_str,
                "weekday": menu.weekday,
                "corners": [
                    {
                        "name": c.name,
                        "time": c.time,
                        "meal": c.meal,
                        "menus": list(c.menus),
                    }
                    for c in menu.corners
                ],
                "restaurants": [
                    {
                        "name": r.name,
                        "category": r.category,
                        "address": r.address,
                        "link": r.link,
                    }
                    for r in sampled
                ],
            }
            task = SendDmTask(
                notification_id=None,
                user_id=row.user_id,
                discord_id=row.discord_id,
                embed=embed,
                payload=payload,
                immediate_send_request_id=row.id,
            )
            await ctx.queue.put(task)
            _logger.info(
                "immediate_send_lunch_queued",
                request_id=row.id,
                user_id=row.user_id,
            )
    except BotException as exc:
        _logger.exception("immediate_send_lunch_failed", code=exc.code)
        await enqueue_admin_alerts(ctx.queue, ctx.settings, CrawlerSource.LUNCH, exc)
