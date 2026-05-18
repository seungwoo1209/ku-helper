from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications.models import Notification, NotificationType


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user(self, user_id: int) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, notification_id: int) -> Notification | None:
        stmt = select(Notification).where(Notification.id == notification_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        type_: NotificationType,
        enabled: bool,
        config: dict[str, Any],
    ) -> Notification:
        notification = Notification(
            user_id=user_id, type=type_, enabled=enabled, config=config
        )
        self._session.add(notification)
        await self._session.flush()
        return notification

    async def update(
        self,
        notification: Notification,
        *,
        enabled: bool | None = None,
        config: dict[str, Any] | None = None,
    ) -> Notification:
        if enabled is not None:
            notification.enabled = enabled
        if config is not None:
            notification.config = config
        await self._session.flush()
        # onupdate=func.now()로 updated_at이 서버 측 값으로 갱신되지만 flush만으로는
        # 파이썬 객체에 반영되지 않아 직렬화 시 lazy-load가 일어난다. refresh로 한 번에 가져온다.
        await self._session.refresh(notification)
        return notification

    async def delete(self, notification: Notification) -> None:
        await self._session.delete(notification)
        await self._session.flush()

    async def delete_all_for_user(self, user_id: int) -> None:
        stmt = delete(Notification).where(Notification.user_id == user_id)
        await self._session.execute(stmt)
        await self._session.flush()
