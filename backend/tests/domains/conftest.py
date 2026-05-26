"""도메인 테스트 공용 픽스처.

`user_factory`, `user`, `authed_client`는 여러 도메인 테스트에서 공유되므로
도메인별 conftest 대신 도메인 루트 conftest에 둔다.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.dependencies import get_current_user
from app.domains.users.models import User, UserRole, UserStatus
from app.main import app

UserFactory = Callable[..., Awaitable[User]]

_DISCORD_ID_BASE = 900_000_000_000_000_000


@pytest_asyncio.fixture
async def user_factory(db_session: AsyncSession) -> UserFactory:
    counter = {"n": 0}

    async def _create(
        *,
        discord_username: str = "tester",
        status: UserStatus = UserStatus.ACTIVE,
        role: UserRole = UserRole.USER,
    ) -> User:
        counter["n"] += 1
        user = User(
            discord_id=_DISCORD_ID_BASE + counter["n"],
            discord_username=discord_username,
            status=status,
            role=role,
        )
        db_session.add(user)
        await db_session.flush()
        return user

    return _create


@pytest_asyncio.fixture
async def user(user_factory: UserFactory) -> User:
    return await user_factory()


@pytest_asyncio.fixture
async def authed_client(
    client: AsyncClient, user: User
) -> AsyncIterator[tuple[AsyncClient, User]]:
    async def _override_get_current_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = _override_get_current_user
    yield client, user
    # client 픽스처가 종료 시 dependency_overrides.clear()로 정리한다.
