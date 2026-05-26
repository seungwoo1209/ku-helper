import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.core.database import Base

# 모델 모듈을 import 해 Base.metadata에 테이블을 등록한다.
from app.domains.notifications import models as _notifications_models  # noqa: F401
from app.domains.users import models as _users_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 운영(IAM 모드) 에서는 Settings.database_url 이 비어있다. alembic 마이그레이션은
# CI 워크플로가 RDS master 패스워드로 조립한 `ALEMBIC_DATABASE_URL` (또는
# 임시 `DATABASE_URL`) 환경변수를 그대로 사용한다. 로컬 dev/test 는 기존대로
# Settings 의 database_url 을 fallback 으로 쓴다.
_alembic_url = (
    os.environ.get("ALEMBIC_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or get_settings().database_url
)
if not _alembic_url:
    raise RuntimeError(
        "ALEMBIC_DATABASE_URL or DATABASE_URL must be set to run alembic"
    )
config.set_main_option("sqlalchemy.url", _alembic_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
