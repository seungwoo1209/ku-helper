from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification, NotificationType, User, UserStatus


class NotificationRepository:
    """`notifications` 테이블 read-only 접근자.

    UPDATE/DELETE 메서드는 정의하지 않는다 — 봇은 알림 설정을 변경할 권한이 없고,
    소프트 삭제·물리 삭제는 백엔드의 cascade 책임이다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_subscriptions(
        self, type_: NotificationType
    ) -> list[Notification]:
        # users.status = ACTIVE 필터를 JOIN으로 적용해 탈퇴 사용자 발송을 1차 차단한다.
        stmt = (
            select(Notification)
            .join(User, User.id == Notification.user_id)
            .where(
                Notification.type == type_,
                Notification.enabled.is_(True),
                User.status == UserStatus.ACTIVE,
            )
            .order_by(Notification.id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
