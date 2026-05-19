"""lifespan 에서 1회 생성 → register_jobs(args=[ctx])."""

import asyncio
from dataclasses import dataclass, field

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.notifications.sender import SendDmTask


@dataclass
class JobContext:
    """잡 함수들이 공유하는 의존성 컨테이너.

    lifespan 에서 1회 인스턴스화하여 register_jobs 에 전달한다.
    in_flight_notification_ids 는 가변 set 이므로 frozen=False.
    """

    queue: asyncio.Queue[SendDmTask]
    http_client: httpx.AsyncClient
    session_maker: async_sessionmaker[AsyncSession]
    settings: Settings
    in_flight_notification_ids: set[int] = field(default_factory=set)
