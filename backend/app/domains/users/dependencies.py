from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import (
    AuthTokenMissing,
    CurrentUserNotFound,
    InvalidAuthToken,
    NotAuthorizedForRole,
    TokenType,
    decode_token,
)
from app.domains.notifications.dependencies import get_notification_repository
from app.domains.notifications.repository import NotificationRepository
from app.domains.users.exceptions import UserDeleted
from app.domains.users.models import User, UserRole, UserStatus
from app.domains.users.repository import UserRepository
from app.domains.users.service import UserService

_bearer_scheme = HTTPBearer(auto_error=False)


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


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    if credentials is None:
        raise AuthTokenMissing()
    payload = decode_token(credentials.credentials, TokenType.ACCESS)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidAuthToken() from exc

    user = await repository.get_by_id(user_id)
    if user is None:
        raise CurrentUserNotFound()
    if user.status == UserStatus.DELETED:
        raise UserDeleted()
    return user


def require_role(role: UserRole) -> Callable[..., Awaitable[User]]:
    """role 가드 의존성을 만든다.

    라우터에서 `admin: Annotated[User, Depends(require_role(UserRole.ADMIN))]` 형태로 합성.
    get_current_user 통과 후 user.role 비교 — DELETED 사용자는 401 이 먼저 거절한다.
    """

    async def _guard(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role != role:
            raise NotAuthorizedForRole()
        return current_user

    return _guard
