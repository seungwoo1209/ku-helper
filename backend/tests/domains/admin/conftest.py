"""admin 도메인 테스트 픽스처.

`admin_authed_client` 는 `authed_client` 의 admin role 변형. tests/domains/conftest.py 의
`user_factory(role=...)` 를 재사용한다.
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.domains.users.models import User, UserRole
from app.main import app
from tests.domains.conftest import UserFactory


@pytest_asyncio.fixture
async def admin_user(user_factory: UserFactory) -> User:
    return await user_factory(role=UserRole.ADMIN)


@pytest_asyncio.fixture
async def admin_authed_client(
    client: AsyncClient, admin_user: User, db_session: AsyncSession
) -> AsyncIterator[tuple[AsyncClient, User]]:
    # authed_client 와 같은 detached User 시나리오 재현 — get_current_user 가 별도 세션에서
    # SELECT 한 결과를 service 에 넘기는 운영 경로를 흉내낸다.
    db_session.expunge(admin_user)

    async def _override_get_current_user() -> User:
        return admin_user

    app.dependency_overrides[get_current_user] = _override_get_current_user
    yield client, admin_user
