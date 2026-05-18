import pytest
from httpx import AsyncClient

from app.core.security import get_current_user
from app.domains.notifications.models import NotificationType
from app.domains.users.models import User
from app.main import app

_BASE = "/api/v1/me/notifications"


@pytest.mark.asyncio
async def test_list_empty(authed_client: tuple[AsyncClient, User]) -> None:
    client, _ = authed_client
    response = await client.get(_BASE)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_transit(authed_client: tuple[AsyncClient, User]) -> None:
    client, user = authed_client
    response = await client.post(
        _BASE,
        json={
            "type": "TRANSIT",
            "config": {
                "station_name": "건대입구",
                "line": "2",
                "minutes_before": 10,
            },
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "TRANSIT"
    assert body["user_id"] == user.id
    assert body["config"]["station_name"] == "건대입구"


@pytest.mark.asyncio
async def test_create_rejects_mismatched_config(
    authed_client: tuple[AsyncClient, User],
) -> None:
    """Discriminated union이라 TRANSIT인데 LUNCH config 키만 보내면 FastAPI가 422."""
    client, _ = authed_client
    response = await client.post(
        _BASE, json={"type": "TRANSIT", "config": {"notify_at": "11:30:00"}}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_enabled_returns_serialized_response(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    """회귀 가드 (b): onupdate=func.now() 컬럼이 flush 후 expired 상태가 되면
    Pydantic 직렬화에서 MissingGreenlet으로 500이 떴다. repository.update에서
    session.refresh를 부르므로 200 + 정상 body가 와야 한다."""
    client, user = authed_client
    notification = await notification_factory(
        user_id=user.id, type_=NotificationType.TRANSIT
    )

    response = await client.patch(f"{_BASE}/{notification.id}", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False


@pytest.mark.asyncio
async def test_patch_config_full_replacement(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    client, user = authed_client
    notification = await notification_factory(
        user_id=user.id, type_=NotificationType.TRANSIT
    )
    response = await client.patch(
        f"{_BASE}/{notification.id}",
        json={
            "config": {
                "station_name": "잠실",
                "line": "2",
                "minutes_before": 5,
                "repeat_interval_minutes": 15,
                "include_congestion": False,
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["config"]["station_name"] == "잠실"


@pytest.mark.asyncio
async def test_patch_invalid_config_returns_domain_error(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    client, user = authed_client
    notification = await notification_factory(
        user_id=user.id, type_=NotificationType.TRANSIT
    )
    response = await client.patch(
        f"{_BASE}/{notification.id}",
        json={"config": {"notify_at": "11:30:00"}},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_NOTIFICATION_CONFIG"


@pytest.mark.asyncio
async def test_get_not_found(authed_client: tuple[AsyncClient, User]) -> None:
    client, _ = authed_client
    response = await client.get(f"{_BASE}/9999")
    assert response.status_code == 404
    assert response.json()["code"] == "NOTIFICATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_other_users_notification_forbidden(
    client: AsyncClient,
    user_factory,
    notification_factory,
) -> None:
    owner = await user_factory(discord_username="owner")
    attacker = await user_factory(discord_username="attacker")
    notification = await notification_factory(
        user_id=owner.id, type_=NotificationType.TRANSIT
    )

    async def _override_get_current_user() -> User:
        return attacker

    app.dependency_overrides[get_current_user] = _override_get_current_user
    response = await client.patch(f"{_BASE}/{notification.id}", json={"enabled": False})
    assert response.status_code == 403
    assert response.json()["code"] == "NOTIFICATION_FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_then_get_404(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    client, user = authed_client
    notification = await notification_factory(
        user_id=user.id, type_=NotificationType.LIBRARY
    )
    delete_resp = await client.delete(f"{_BASE}/{notification.id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"{_BASE}/{notification.id}")
    assert get_resp.status_code == 404
