import asyncio
import random

import structlog

from app.admin.alerts import CrawlerSource, maybe_enqueue_admin_alerts
from app.core.database import async_session_maker
from app.core.exceptions import BotException
from app.crawlers.lunch.exceptions import LunchCrawlerFailed
from app.crawlers.restaurants.exceptions import RestaurantsCrawlerFailed
from app.db.models import NotificationDeliveryStatus, NotificationType
from app.notifications.history_repository import NotificationHistoryRepository
from app.notifications.lunch.embeds import build_lunch_immediate_embed
from app.notifications.lunch.repository import ImmediateSendRequestRepository
from app.notifications.repository import NotificationRepository
from app.notifications.sender import SendDmTask
from app.scheduler.context import JobContext

_logger = structlog.get_logger(__name__)

_RESTAURANTS_SAMPLE_SIZE = 3
_POLL_LIMIT = 50


async def run_lunch_job() -> None:
    """정기 LUNCH 구독 폴링 (§C-4 후속). 현재는 활성 구독 수만 로그."""
    try:
        async with async_session_maker() as session:
            repo = NotificationRepository(session)
            subs = await repo.list_active_subscriptions(NotificationType.LUNCH)
        _logger.info("lunch_poll_tick", count=len(subs))
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
                await maybe_enqueue_admin_alerts(
                    ctx.queue, ctx.redis_client, ctx.settings, source, exc
                )
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
        await maybe_enqueue_admin_alerts(
            ctx.queue, ctx.redis_client, ctx.settings, CrawlerSource.LUNCH, exc
        )
