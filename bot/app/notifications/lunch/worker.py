import asyncio
import random

import structlog

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

    중복 적재는 ctx.lunch_inflight set 으로 방지. Sender 가 history INSERT 한 뒤
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
            if row.id in ctx.lunch_inflight:
                continue
            ctx.lunch_inflight.add(row.id)
            try:
                menu, pool = await asyncio.gather(
                    lunch_client.fetch_today_menu(),
                    restaurants_client.fetch_pool(),
                )
            except (LunchCrawlerFailed, RestaurantsCrawlerFailed) as exc:
                # 발송 실패도 history 에 1건 적재해 다음 폴링에서 자연 제외.
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
                ctx.lunch_inflight.discard(row.id)
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
