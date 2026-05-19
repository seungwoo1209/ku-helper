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

    async def list_active_subscriptions_with_user(
        self, type_: NotificationType
    ) -> list[tuple[Notification, User]]:
        """활성 구독을 User 와 함께 조회한다.

        list_active_subscriptions 와 동일한 WHERE 절. Worker 가 user.discord_id 등을
        별도 조회 없이 바로 사용할 수 있도록 User 컬럼도 SELECT 에 포함한다.
        기존 list_active_subscriptions 는 건드리지 않는다 — lunch/library stub 이 사용 중.
        """
        stmt = (
            select(Notification, User)
            .join(User, User.id == Notification.user_id)
            .where(
                Notification.type == type_,
                Notification.enabled.is_(True),
                User.status == UserStatus.ACTIVE,
            )
            .order_by(Notification.id)
        )
        result = await self._session.execute(stmt)
        return list(result.tuples().all())

    async def get_user_status(self, user_id: int) -> UserStatus | None:
        """user_id 에 해당하는 사용자의 status 를 반환한다.

        사용자 행이 없으면 None 을 반환한다.
        Sender 워커의 이중 가드(발송 직전 재검증)에서 사용.
        """
        stmt = select(User.status).where(User.id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row
