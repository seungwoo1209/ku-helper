from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.domains.immediate_send.repository import ImmediateSendRepository
from app.domains.immediate_send.service import ImmediateSendService


def get_immediate_send_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImmediateSendRepository:
    return ImmediateSendRepository(session)


def get_immediate_send_service(
    repository: Annotated[
        ImmediateSendRepository, Depends(get_immediate_send_repository)
    ],
) -> ImmediateSendService:
    return ImmediateSendService(repository)
