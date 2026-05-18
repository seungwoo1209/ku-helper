import structlog

from app.core.database import async_session_maker
from app.core.exceptions import BotException
from app.db.models import NotificationType
from app.notifications.repository import NotificationRepository

_logger = structlog.get_logger(__name__)


async def run_library_job() -> None:
    """LIBRARY 활성 구독을 폴링한다.

    임계값 비교·F-14 상태 머신·임베드·Sender 큐 적재는 roadmap §D.
    """
    try:
        async with async_session_maker() as session:
            repo = NotificationRepository(session)
            subs = await repo.list_active_subscriptions(NotificationType.LIBRARY)
        _logger.info("library_poll_tick", count=len(subs))
    except BotException as exc:
        _logger.exception("library_poll_failed", code=exc.code)
