from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.domains.users.repository import UserRepository


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRepository:
    return UserRepository(session)
