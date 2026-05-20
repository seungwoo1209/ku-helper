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


# ---------------------------------------------------------------------------
# Create — F-06 / F-07 / F-12 / F-15 변형
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_transit_arrival(authed_client: tuple[AsyncClient, User]) -> None:
    """F-06: mode=arrival + minutes_before."""
    client, user = authed_client
    response = await client.post(
        _BASE,
        json={
            "type": "TRANSIT",
            "config": {
                "mode": "arrival",
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
    assert body["config"]["mode"] == "arrival"
    assert body["config"]["minutes_before"] == 10


@pytest.mark.asyncio
async def test_create_transit_recurring(
    authed_client: tuple[AsyncClient, User],
) -> None:
    """F-07: mode=recurring + start/end + interval."""
    client, _ = authed_client
    response = await client.post(
        _BASE,
        json={
            "type": "TRANSIT",
            "config": {
                "mode": "recurring",
                "station_name": "잠실",
                "line": "2",
                "start_time": "09:00:00",
                "end_time": "10:00:00",
                "repeat_interval_minutes": 5,
            },
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["config"]["mode"] == "recurring"
    assert body["config"]["repeat_interval_minutes"] == 5


@pytest.mark.asyncio
async def test_create_transit_recurring_rejects_end_before_start(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authed_client
    response = await client.post(
        _BASE,
        json={
            "type": "TRANSIT",
            "config": {
                "mode": "recurring",
                "station_name": "잠실",
                "line": "2",
                "start_time": "10:00:00",
                "end_time": "09:00:00",
                "repeat_interval_minutes": 5,
            },
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_transit_arrival_missing_minutes_before(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authed_client
    response = await client.post(
        _BASE,
        json={
            "type": "TRANSIT",
            "config": {
                "mode": "arrival",
                "station_name": "건대입구",
                "line": "2",
            },
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_lunch_highlight_default_true(
    authed_client: tuple[AsyncClient, User],
) -> None:
    """F-12: highlight_today_pick는 기본 True."""
    client, _ = authed_client
    response = await client.post(
        _BASE,
        json={"type": "LUNCH", "config": {"notify_at": "11:30:00"}},
    )
    assert response.status_code == 201
    assert response.json()["config"]["highlight_today_pick"] is True


@pytest.mark.asyncio
async def test_create_lunch_highlight_off(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authed_client
    response = await client.post(
        _BASE,
        json={
            "type": "LUNCH",
            "config": {"notify_at": "11:30:00", "highlight_today_pick": False},
        },
    )
    assert response.status_code == 201
    assert response.json()["config"]["highlight_today_pick"] is False


@pytest.mark.asyncio
async def test_create_library_urgent_above_threshold_rejected(
    authed_client: tuple[AsyncClient, User],
) -> None:
    """F-15: urgent_threshold > threshold이면 422."""
    client, _ = authed_client
    response = await client.post(
        _BASE,
        json={
            "type": "LIBRARY",
            "config": {
                "reading_room_id": 1,
                "threshold": 5,
                "urgent_threshold": 10,
            },
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_mismatched_config(
    authed_client: tuple[AsyncClient, User],
) -> None:
    """Discriminated union: TRANSIT인데 LUNCH config 키만 보내면 422."""
    client, _ = authed_client
    response = await client.post(
        _BASE, json={"type": "TRANSIT", "config": {"notify_at": "11:30:00"}}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Type별 list 엔드포인트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_transit_only(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    """GET /transit는 같은 사용자의 TRANSIT 알림만 반환한다."""
    client, user = authed_client
    await notification_factory(user_id=user.id, type_=NotificationType.TRANSIT)
    await notification_factory(user_id=user.id, type_=NotificationType.LUNCH)
    await notification_factory(user_id=user.id, type_=NotificationType.LIBRARY)

    response = await client.get(f"{_BASE}/transit")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "TRANSIT"
    assert body[0]["config"]["mode"] == "arrival"


@pytest.mark.asyncio
async def test_list_lunch_only(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    client, user = authed_client
    await notification_factory(user_id=user.id, type_=NotificationType.TRANSIT)
    await notification_factory(user_id=user.id, type_=NotificationType.LUNCH)

    response = await client.get(f"{_BASE}/lunch")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "LUNCH"


@pytest.mark.asyncio
async def test_list_library_empty(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    """다른 type만 있는 경우 LIBRARY list는 빈 배열."""
    client, user = authed_client
    await notification_factory(user_id=user.id, type_=NotificationType.TRANSIT)

    response = await client.get(f"{_BASE}/library")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_transit_isolates_users(
    client: AsyncClient,
    user_factory,
    notification_factory,
) -> None:
    """다른 사용자의 TRANSIT 알림은 노출되지 않는다."""
    me = await user_factory(discord_username="me")
    other = await user_factory(discord_username="other")
    await notification_factory(user_id=other.id, type_=NotificationType.TRANSIT)

    async def _override_get_current_user() -> User:
        return me

    app.dependency_overrides[get_current_user] = _override_get_current_user
    response = await client.get(f"{_BASE}/transit")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Read — discriminated union이 type별 정확한 스키마로 직렬화하는지
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_typed_config(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    client, user = authed_client
    n = await notification_factory(user_id=user.id, type_=NotificationType.TRANSIT)
    response = await client.get(f"{_BASE}/{n.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "TRANSIT"
    # JSONB에 저장된 mode discriminator가 응답에도 그대로 노출되어야 한다.
    assert body["config"]["mode"] == "arrival"


# ---------------------------------------------------------------------------
# PATCH — type별 분리 엔드포인트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_transit_enabled(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    """회귀 가드 (b): onupdate=func.now() 컬럼이 flush 후 expired 상태가 되면
    Pydantic 직렬화에서 MissingGreenlet으로 500이 떴다. repository.update에서
    session.refresh를 부르므로 200 + 정상 body가 와야 한다."""
    client, user = authed_client
    n = await notification_factory(user_id=user.id, type_=NotificationType.TRANSIT)

    response = await client.patch(f"{_BASE}/transit/{n.id}", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False


@pytest.mark.asyncio
async def test_patch_transit_full_config_replace(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    client, user = authed_client
    n = await notification_factory(user_id=user.id, type_=NotificationType.TRANSIT)
    response = await client.patch(
        f"{_BASE}/transit/{n.id}",
        json={
            "config": {
                "mode": "recurring",
                "station_name": "잠실",
                "line": "2",
                "start_time": "09:00:00",
                "end_time": "10:00:00",
                "repeat_interval_minutes": 15,
                "include_congestion": False,
            }
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["config"]["mode"] == "recurring"
    assert body["config"]["station_name"] == "잠실"


@pytest.mark.asyncio
async def test_patch_lunch_full_config_replace(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    client, user = authed_client
    n = await notification_factory(user_id=user.id, type_=NotificationType.LUNCH)
    response = await client.patch(
        f"{_BASE}/lunch/{n.id}",
        json={
            "config": {
                "notify_at": "12:00:00",
                "max_price": 9000,
                "recommend_count": 5,
                "highlight_today_pick": False,
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["config"]["max_price"] == 9000
    assert response.json()["config"]["highlight_today_pick"] is False


@pytest.mark.asyncio
async def test_patch_wrong_type_endpoint_returns_404(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    """LUNCH 알림을 transit 엔드포인트로 접근하면 type mismatch → 404 마스킹."""
    client, user = authed_client
    n = await notification_factory(user_id=user.id, type_=NotificationType.LUNCH)
    response = await client.patch(f"{_BASE}/transit/{n.id}", json={"enabled": False})
    assert response.status_code == 404
    assert response.json()["code"] == "NOTIFICATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_invalid_config_returns_422(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    """타입별 엔드포인트라 잘못된 config는 Pydantic이 라우터 단에서 422로 반환."""
    client, user = authed_client
    n = await notification_factory(user_id=user.id, type_=NotificationType.TRANSIT)
    response = await client.patch(
        f"{_BASE}/transit/{n.id}",
        json={"config": {"notify_at": "11:30:00"}},
    )
    assert response.status_code == 422


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
    n = await notification_factory(user_id=owner.id, type_=NotificationType.TRANSIT)

    async def _override_get_current_user() -> User:
        return attacker

    app.dependency_overrides[get_current_user] = _override_get_current_user
    response = await client.patch(f"{_BASE}/transit/{n.id}", json={"enabled": False})
    assert response.status_code == 403
    assert response.json()["code"] == "NOTIFICATION_FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_then_get_404(
    authed_client: tuple[AsyncClient, User],
    notification_factory,
) -> None:
    client, user = authed_client
    n = await notification_factory(user_id=user.id, type_=NotificationType.LIBRARY)
    delete_resp = await client.delete(f"{_BASE}/{n.id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"{_BASE}/{n.id}")
    assert get_resp.status_code == 404
