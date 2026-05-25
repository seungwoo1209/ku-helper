from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.aws_auth import generate_rds_iam_token
from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def _build_engine_url_and_args(settings: Settings) -> tuple[str, dict[str, object]]:
    if settings.use_iam_auth:
        url = (
            f"postgresql+asyncpg://{settings.db_iam_user}@{settings.db_host}:"
            f"{settings.db_port}/{settings.db_name}"
        )
        return url, {"ssl": "require"}
    return settings.database_url, {}


_settings = get_settings()
_url, _connect_args = _build_engine_url_and_args(_settings)

engine = create_async_engine(_url, future=True, connect_args=_connect_args)
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


if _settings.use_iam_auth:
    @event.listens_for(engine.sync_engine, "do_connect")
    def _inject_rds_iam_password(
        _dialect: object,
        _conn_rec: object,
        _cargs: tuple[object, ...],
        cparams: dict[str, object],
    ) -> None:
        # RDS IAM 토큰은 15분 만료. 매 connect 시점에 새로 발급해 connection pool 이
        # 만료된 토큰을 재사용하지 않도록 한다.
        cparams["password"] = generate_rds_iam_token(
            host=_settings.db_host,
            port=_settings.db_port,
            user=_settings.db_iam_user,
            region=_settings.aws_region,
        )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
