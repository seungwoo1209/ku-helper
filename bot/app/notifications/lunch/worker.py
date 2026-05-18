import structlog

from app.core.database import async_session_maker
from app.core.exceptions import BotException
from app.db.models import NotificationType
from app.notifications.repository import NotificationRepository

_logger = structlog.get_logger(__name__)


async def run_lunch_job() -> None:
    """LUNCH 활성 구독을 폴링한다.

    조건 평가(`notify_at` 매칭)·크롤링·임베드·Sender 큐 적재는 roadmap §C.
    """
    try:
        async with async_session_maker() as session:
            repo = NotificationRepository(session)
            subs = await repo.list_active_subscriptions(NotificationType.LUNCH)
        _logger.info("lunch_poll_tick", count=len(subs))
    except BotException as exc:
        _logger.exception("lunch_poll_failed", code=exc.code)
