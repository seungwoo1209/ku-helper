"""실 JWT + 실 DB 로 인증 가드 동작을 검증한다.

`tests/domains/conftest.py` 의 `authed_client` 는 `dependency_overrides[get_current_user]`
로 가드를 우회하므로, "토큰은 유효한데 DB row 가 DELETED" 같은 경로가 실제로 통합
스택에서 차단되는지 확인하지 못한다. 본 모듈은 override 없이 실 토큰 + 실 DB 상태로
가드 양 끝(만료·DELETED)을 한 번씩 통과시킨다.
"""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.domains.users.models import UserStatus
from tests.domains.conftest import UserFactory


@pytest.mark.asyncio
async def test_get_me_with_deleted_user_returns_401_user_deleted(
    client: AsyncClient,
    user_factory: UserFactory,
) -> None:
    user = await user_factory(
        discord_username="deleted-via-real-jwt", status=UserStatus.DELETED
    )
    token = create_access_token(user_id=user.id, discord_id=user.discord_id)

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "USER_DELETED"


@pytest.mark.asyncio
async def test_get_me_with_active_user_returns_profile(
    client: AsyncClient,
    user_factory: UserFactory,
) -> None:
    """위 가드가 단순히 "항상 401" 이 아님을 보장하는 짝꿍 케이스."""
    user = await user_factory(discord_username="active-via-real-jwt")
    token = create_access_token(user_id=user.id, discord_id=user.discord_id)

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["discord_id"] == user.discord_id
