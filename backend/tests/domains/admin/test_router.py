"""`GET /api/v1/admin/health` — require_role(ADMIN) 가드 검증.

본 엔드포인트 자체는 ping 이고, 의도는 require_role 가드 동작을 회귀로 막는 것이다.
F-23 의 admin 엔드포인트들이 모두 같은 가드 패턴을 따른다.
"""

import pytest
from httpx import AsyncClient

from app.domains.users.models import User


@pytest.mark.asyncio
async def test_admin_health_returns_ok_for_admin(
    admin_authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = admin_authed_client
    response = await client.get("/api/v1/admin/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_admin_health_forbidden_for_regular_user(
    authed_client: tuple[AsyncClient, User],
) -> None:
    """USER role 사용자는 403 NOT_AUTHORIZED_FOR_ROLE."""
    client, _ = authed_client
    response = await client.get("/api/v1/admin/health")
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "NOT_AUTHORIZED_FOR_ROLE"


@pytest.mark.asyncio
async def test_admin_health_unauthenticated(client: AsyncClient) -> None:
    """JWT 토큰 자체가 없으면 401 AUTH_TOKEN_MISSING — require_role 진입 전 차단."""
    response = await client.get("/api/v1/admin/health")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_TOKEN_MISSING"
