"""notification_history INSERT 전용 Repository.

UPDATE/DELETE 메서드는 정의하지 않는다 — 봇은 INSERT 권한만 가지며,
CASCADE 삭제는 백엔드의 책임이다 (architecture.md, security.md).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NotificationDeliveryStatus, NotificationHistory


class NotificationHistoryRepository:
    """`notification_history` INSERT 전용 접근자."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_last_sent_at(
        self,
        notification_id: int,
        status: NotificationDeliveryStatus,
    ) -> datetime | None:
        """지정 notification_id + status 의 가장 최근 sent_at 을 반환한다.

        이력이 없으면 None. Worker 가 발송 간격(F-07 interval) 준수 여부를 판단하는 데 사용.
        """
        stmt = (
            select(NotificationHistory.sent_at)
            .where(
                NotificationHistory.notification_id == notification_id,
                NotificationHistory.status == status,
            )
            .order_by(NotificationHistory.sent_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def insert_result(
        self,
        *,
        notification_id: int | None,
        user_id: int,
        status: NotificationDeliveryStatus,
        payload: dict[str, Any],
        failure_reason: str | None = None,
        immediate_send_request_id: int | None = None,
    ) -> None:
        """발송 결과 1행을 INSERT + flush한다.

        commit 은 호출자(Sender 워커) 책임.
        notification_id 와 immediate_send_request_id 둘 다 None 가능: 관리자 알림(F-22).
        둘 중 하나만 set 되는 것이 일반적 (정기 알림 vs 즉시 발송).
        """
        row = NotificationHistory(
            notification_id=notification_id,
            immediate_send_request_id=immediate_send_request_id,
            user_id=user_id,
            status=status,
            payload=payload,
            failure_reason=failure_reason,
        )
        self._session.add(row)
        await self._session.flush()
