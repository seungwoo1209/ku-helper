from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.immediate_send.models import ImmediateSendRequest
from app.domains.notifications.models import (
    Notification,
    NotificationDeliveryStatus,
    NotificationHistory,
    NotificationType,
)


@dataclass(frozen=True)
class NotificationHistoryView:
    """F-17 응답 빌드용 뷰. Repository 가 raw Row 를 그대로 흘리지 않도록
    `NotificationHistory` 와 LEFT JOIN COALESCE 로 도출한 `type` 을 묶어 둔 컨테이너.
    """

    history: NotificationHistory
    type: NotificationType


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

    async def list_by_user_and_type(
        self, user_id: int, type_: NotificationType
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id, Notification.type == type_)
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

    async def delete_history_for_user(self, user_id: int) -> None:
        stmt = delete(NotificationHistory).where(NotificationHistory.user_id == user_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def list_history_for_user(
        self,
        user_id: int,
        *,
        sent_at_from: datetime,
        sent_at_to: datetime,
        type_: NotificationType | None,
        status: NotificationDeliveryStatus | None,
        limit: int,
    ) -> list[NotificationHistoryView]:
        """F-17 알림 발송 이력 조회. `type` 컬럼은 history 본체에 없으므로
        `Notification` / `ImmediateSendRequest` 와 LEFT JOIN 후 COALESCE 로 도출한다.

        관리자(F-22) 알림 row 는 양 FK 가 모두 NULL 로 적재되므로 WHERE 절에서 제외한다
        — F-17 은 사용자의 알림 이력만을 대상으로 한다는 정책(§E-1 합의 전 Plan A).
        """
        type_expr = func.coalesce(Notification.type, ImmediateSendRequest.type)
        stmt = (
            select(NotificationHistory, type_expr.label("derived_type"))
            .outerjoin(
                Notification,
                NotificationHistory.notification_id == Notification.id,
            )
            .outerjoin(
                ImmediateSendRequest,
                NotificationHistory.immediate_send_request_id
                == ImmediateSendRequest.id,
            )
            .where(NotificationHistory.user_id == user_id)
            .where(NotificationHistory.sent_at >= sent_at_from)
            .where(NotificationHistory.sent_at < sent_at_to)
            .where(
                or_(
                    NotificationHistory.notification_id.is_not(None),
                    NotificationHistory.immediate_send_request_id.is_not(None),
                )
            )
            .order_by(NotificationHistory.sent_at.desc())
            .limit(limit)
        )
        if type_ is not None:
            stmt = stmt.where(type_expr == type_)
        if status is not None:
            stmt = stmt.where(NotificationHistory.status == status)

        result = await self._session.execute(stmt)
        return [NotificationHistoryView(history=h, type=t) for h, t in result.all()]
