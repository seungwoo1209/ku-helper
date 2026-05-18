import structlog

from app.core.database import async_session_maker
from app.core.exceptions import BotException
from app.db.models import NotificationType
from app.notifications.repository import NotificationRepository

_logger = structlog.get_logger(__name__)


async def run_transit_job() -> None:
    """TRANSIT 활성 구독을 폴링한다.

    조건 평가·외부 API 호출·임베드 빌드·Sender 큐 적재는 후속 PR(roadmap §B).
    이 단계에서는 폴링 경로가 살아 있는지를 로그 1줄로 검증한다.
    """
    try:
        async with async_session_maker() as session:
            repo = NotificationRepository(session)
            subs = await repo.list_active_subscriptions(NotificationType.TRANSIT)
        _logger.info("transit_poll_tick", count=len(subs))
    except BotException as exc:
        # 다음 트리거를 막지 않도록 swallow. F-22 카운터는 §E에서 추가한다.
        _logger.exception("transit_poll_failed", code=exc.code)
