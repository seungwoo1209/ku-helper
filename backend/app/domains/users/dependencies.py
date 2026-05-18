from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.domains.notifications.dependencies import get_notification_repository
from app.domains.notifications.repository import NotificationRepository
from app.domains.users.repository import UserRepository
from app.domains.users.service import UserService


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRepository:
    return UserRepository(session)


def get_user_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    notification_repository: Annotated[
        NotificationRepository, Depends(get_notification_repository)
    ],
) -> UserService:
    return UserService(repository, notification_repository)
