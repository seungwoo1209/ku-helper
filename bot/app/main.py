import asyncio

import discord
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import async_session_maker, engine
from app.core.discord import DiscordBotClient
from app.core.logging import configure_logging
from app.core.redis import create_redis_client
from app.notifications.sender import SendDmTask, run_sender_worker
from app.scheduler.jobs import register_jobs

# models 모듈은 Base.metadata에 테이블을 등록하기 위해 import만 해 두면 됨.
from app.db import models as _models  # noqa: F401


async def _verify_database() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def main() -> None:
    configure_logging()
    logger = structlog.get_logger(__name__)
    settings = get_settings()

    logger.info("bot_startup_begin", environment=settings.environment)

    await _verify_database()
    logger.info("database_ready")

    redis_client: Redis | None = None
    if settings.redis_url:
        redis_client = await create_redis_client(settings.redis_url)
        logger.info("redis_ready")
    else:
        logger.warning("redis_skipped_no_url")

    scheduler = AsyncIOScheduler()
    register_jobs(scheduler)
    scheduler.start()
    logger.info("scheduler_started", job_count=len(scheduler.get_jobs()))

    # 인텐트 최소화 — DM 발송만 수행하므로 기본값으로 충분.
    dc_client = discord.Client(intents=discord.Intents.default())
    dc_bot_client = DiscordBotClient(dc_client, settings)

    # Sender 큐 + 워커 태스크. discord.Client.start() 는 블로킹이므로
    # 워커를 먼저 task 로 띄운다. 워커 내부에서 wait_until_ready() 로 ready 대기.
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    sender_task = asyncio.create_task(
        run_sender_worker(queue, dc_bot_client, async_session_maker)
    )

    try:
        logger.info("discord_client_starting")
        await dc_bot_client.start()
    finally:
        logger.info("bot_shutdown_begin")
        sender_task.cancel()
        await asyncio.gather(sender_task, return_exceptions=True)
        scheduler.shutdown(wait=False)
        await dc_bot_client.close()
        if redis_client is not None:
            await redis_client.aclose()
        await engine.dispose()
        logger.info("bot_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
