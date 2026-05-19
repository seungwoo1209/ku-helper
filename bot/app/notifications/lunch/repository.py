"""ImmediateSendRequest read-only repository.

봇은 immediate_send_requests 행을 INSERT/UPDATE/DELETE 하지 않는다 — 백엔드 책임.
fulfilled 판별은 notification_history.immediate_send_request_id FK LEFT JOIN 으로.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ImmediateSendRequest,
    NotificationHistory,
    NotificationType,
    User,
    UserStatus,
)


@dataclass(frozen=True)
class ImmediateSendRequestRow:
    """폴링 쿼리 결과 한 건. ORM 객체 노출 회피용 평탄화 dataclass."""

    id: int
    user_id: int
    discord_id: int
    payload: dict[str, Any]


class ImmediateSendRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_pending(
        self, type_: NotificationType, limit: int = 50
    ) -> list[ImmediateSendRequestRow]:
        """미발송 즉시 요청을 조회한다.

        notification_history.immediate_send_request_id LEFT JOIN 으로
        이미 처리된 row 를 제외한다. ACTIVE 사용자만 노출.
        """
        stmt = (
            select(
                ImmediateSendRequest.id,
                ImmediateSendRequest.user_id,
                User.discord_id,
                ImmediateSendRequest.payload,
            )
            .join(User, User.id == ImmediateSendRequest.user_id)
            .outerjoin(
                NotificationHistory,
                NotificationHistory.immediate_send_request_id
                == ImmediateSendRequest.id,
            )
            .where(
                ImmediateSendRequest.type == type_,
                User.status == UserStatus.ACTIVE,
                NotificationHistory.id.is_(None),
            )
            .order_by(ImmediateSendRequest.id)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            ImmediateSendRequestRow(
                id=row.id,
                user_id=row.user_id,
                discord_id=row.discord_id,
                payload=row.payload,
            )
            for row in result.all()
        ]
