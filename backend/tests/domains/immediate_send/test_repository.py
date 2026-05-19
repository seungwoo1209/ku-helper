import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.immediate_send.models import ImmediateSendRequest
from app.domains.immediate_send.repository import ImmediateSendRepository
from app.domains.notifications.models import NotificationType
from app.domains.users.models import User


@pytest.mark.asyncio
async def test_create_inserts_row_with_defaults(
    db_session: AsyncSession,
    user: User,
) -> None:
    repository = ImmediateSendRepository(db_session)

    request = await repository.create(
        user_id=user.id, type_=NotificationType.LUNCH, payload={}
    )

    assert request.id is not None
    assert request.user_id == user.id
    assert request.type == NotificationType.LUNCH
    assert request.payload == {}
    assert request.requested_at is not None

    # row 가 실제 DB 에 들어갔는지 재조회로 확인.
    result = await db_session.execute(
        select(ImmediateSendRequest).where(ImmediateSendRequest.id == request.id)
    )
    fetched = result.scalar_one()
    assert fetched.user_id == user.id
