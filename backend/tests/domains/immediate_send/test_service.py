from typing import Any

import pytest

from app.domains.immediate_send.models import ImmediateSendRequest
from app.domains.immediate_send.service import ImmediateSendService
from app.domains.notifications.models import NotificationType
from app.domains.users.models import User, UserRole, UserStatus


class _FakeRepository:
    def __init__(self) -> None:
        self.created: list[tuple[int, NotificationType, dict[str, Any]]] = []
        self._next_id = 100

    async def create(
        self,
        *,
        user_id: int,
        type_: NotificationType,
        payload: dict[str, Any],
    ) -> ImmediateSendRequest:
        self.created.append((user_id, type_, payload))
        request = ImmediateSendRequest(
            id=self._next_id, user_id=user_id, type=type_, payload=payload
        )
        self._next_id += 1
        return request


@pytest.mark.asyncio
async def test_request_lunch_dispatch_calls_repository_with_lunch_type() -> None:
    repo = _FakeRepository()
    service = ImmediateSendService(repo)  # type: ignore[arg-type]
    user = User(
        id=42,
        discord_id=123456789,
        discord_username="tester",
        status=UserStatus.ACTIVE,
        role=UserRole.USER,
    )

    request = await service.request_lunch_dispatch(user)

    assert request.type == NotificationType.LUNCH
    assert request.user_id == 42
    assert repo.created == [(42, NotificationType.LUNCH, {})]
