from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
engine = create_async_engine(_settings.database_url, future=True)
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncIterator[AsyncSession]:
    # 봇은 잡 함수가 트랜잭션 경계를 직접 잡는다. 여기서는 세션만 열고 닫는다.
    # 커밋·롤백 책임은 호출 측에 있음.
    async with async_session_maker() as session:
        yield session
