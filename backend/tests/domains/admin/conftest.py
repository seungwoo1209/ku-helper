"""admin 도메인 테스트 픽스처.

`admin_authed_client` 는 `authed_client` 의 admin role 변형. tests/domains/conftest.py 의
`user_factory(role=...)` 를 재사용한다.
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import AsyncClient

from app.domains.users.dependencies import get_current_user
from app.domains.users.models import User, UserRole
from app.main import app
from tests.domains.conftest import UserFactory


@pytest_asyncio.fixture
async def admin_user(user_factory: UserFactory) -> User:
    return await user_factory(role=UserRole.ADMIN)


@pytest_asyncio.fixture
async def admin_authed_client(
    client: AsyncClient, admin_user: User
) -> AsyncIterator[tuple[AsyncClient, User]]:
    async def _override_get_current_user() -> User:
        return admin_user

    app.dependency_overrides[get_current_user] = _override_get_current_user
    yield client, admin_user
