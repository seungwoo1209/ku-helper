from typing import Any

import pytest

from app.domains.immediate_send.models import ImmediateSendRequest
from app.domains.immediate_send.schemas import (
    LibraryDispatchRequest,
    TransitDispatchRequest,
)
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


@pytest.mark.asyncio
async def test_request_transit_dispatch_calls_repository_with_transit_payload() -> None:
    repo = _FakeRepository()
    service = ImmediateSendService(repo)  # type: ignore[arg-type]
    user = User(
        id=7,
        discord_id=987654321,
        discord_username="commuter",
        status=UserStatus.ACTIVE,
        role=UserRole.USER,
    )
    body = TransitDispatchRequest(station_name="강남", line="2호선")

    request = await service.request_transit_dispatch(user, body)

    assert request.type == NotificationType.TRANSIT
    assert request.user_id == 7
    assert repo.created == [
        (7, NotificationType.TRANSIT, {"station_name": "강남", "line": "2호선"})
    ]


@pytest.mark.asyncio
async def test_request_library_dispatch_calls_repository_with_library_payload() -> None:
    repo = _FakeRepository()
    service = ImmediateSendService(repo)  # type: ignore[arg-type]
    user = User(
        id=9,
        discord_id=555555555,
        discord_username="reader",
        status=UserStatus.ACTIVE,
        role=UserRole.USER,
    )
    body = LibraryDispatchRequest(reading_room_id=1)

    request = await service.request_library_dispatch(user, body)

    assert request.type == NotificationType.LIBRARY
    assert request.user_id == 9
    assert repo.created == [(9, NotificationType.LIBRARY, {"reading_room_id": 1})]
