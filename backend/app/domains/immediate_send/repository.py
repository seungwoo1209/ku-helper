from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.immediate_send.models import ImmediateSendRequest
from app.domains.notifications.models import NotificationType


class ImmediateSendRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        type_: NotificationType,
        payload: dict[str, Any],
    ) -> ImmediateSendRequest:
        request = ImmediateSendRequest(user_id=user_id, type=type_, payload=payload)
        self._session.add(request)
        await self._session.flush()
        await self._session.refresh(request)
        return request
