"""전역 픽스처.

테스트 DB 격리 전략은 다음 두 사실을 활용한다.

1. Service/Repository는 절대 `session.commit()`을 호출하지 않는다 (CLAUDE.md·
   architecture.md 규칙). 커밋은 평소 `app.core.database.get_session`이 yield 직후
   호출하지만, 테스트의 `client` 픽스처가 `get_session`을 override하여 그
   commit/rollback 단계를 생략한다.
2. 따라서 라우터가 만든 모든 변경은 한 세션 안에서만 보이고, 세션이 닫히면
   자동 rollback된다. 매 테스트가 새 `AsyncSession`을 받으므로 누설이 없다.

NullPool로 connection 재사용도 차단해 다른 테스트의 idle connection이 데이터를
캐리하는 일도 없다. 스키마 셋업은 `Base.metadata.create_all` 한 번. 마이그레이션
자체의 회귀 검증은 별 작업이다.
"""

from __future__ import annotations

import os

# Settings 의 validator 는 use_iam_auth=False 일 때 DATABASE_URL / REDIS_URL 을 둘 다
# 요구한다. 테스트는 실 DB 는 test_engine 픽스처로, redis 는 fakeredis 로 오버라이드
# 하지만 Settings 인스턴스화 자체에 문자열이 필요하므로 placeholder 를 미리 주입.
# app.main 임포트 시점에 get_settings() 가 호출되므로 반드시 그 이전에 설정.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://ku_helper:ku_helper_test@localhost:5433/ku_helper_test",
)

from collections.abc import AsyncIterator  # noqa: E402

import fakeredis.aioredis  # noqa: E402
import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from redis.asyncio import Redis  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.database import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402

_DEFAULT_TEST_DB_URL = (
    "postgresql+asyncpg://ku_helper:ku_helper_test@localhost:5433/ku_helper_test"
)


def _test_db_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB_URL)


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(_test_db_url(), future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _ensure_app_http_client() -> AsyncIterator[None]:
    # ASGITransport는 lifespan을 자동으로 돌리지 않는다. auth 의존성이
    # `request.app.state.http_client`를 참조하므로 세션 내내 살아 있는 클라이언트를
    # 세팅한다. respx가 이 클라이언트의 트래픽을 가로채는 데 사용된다.
    created_here = False
    if not hasattr(app.state, "http_client"):
        app.state.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0)
        )
        created_here = True
    try:
        yield
    finally:
        if created_here:
            await app.state.http_client.aclose()
            del app.state.http_client


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[Redis]:
    """매 테스트마다 비어 있는 fakeredis 인스턴스 + app.state.redis 오버라이드.

    auth 의존성이 `request.app.state.redis` 를 참조하므로 client 픽스처가 잡히기 전에
    state 를 세팅해 둔다. 테스트 종료 후 attribute 를 정리해 다음 테스트로 누설 방지.
    """
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.redis = fake
    try:
        yield fake
    finally:
        await fake.aclose()
        if hasattr(app.state, "redis"):
            del app.state.redis


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    redis_client: Redis,
) -> AsyncIterator[AsyncClient]:
    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        # commit/rollback은 의도적으로 생략한다 (위 docstring 참조).
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
