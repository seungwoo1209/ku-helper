from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.domains.notifications.repository import NotificationRepository
from app.domains.notifications.service import NotificationService


def get_notification_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationRepository:
    return NotificationRepository(session)


def get_notification_service(
    repository: Annotated[NotificationRepository, Depends(get_notification_repository)],
) -> NotificationService:
    return NotificationService(repository)
