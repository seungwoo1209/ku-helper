"""lifespan 에서 1회 생성 → register_jobs(args=[ctx])."""

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.notifications.sender import SendDmTask

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.crawlers.lunch.client import LunchClient
    from app.crawlers.restaurants.client import RestaurantsClient


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
    # §C-3 즉시 발송 lunch worker 가 사용. lifespan 에서 lunch_client·restaurants_client 가
    # 만들어지지 못한 경우(키 미설정 등) None 이며 worker 는 skip.
    lunch_client: "LunchClient | None" = None
    restaurants_client: "RestaurantsClient | None" = None
    # lunch + transit 즉시 발송 worker 가 공유. request_id 단일 시퀀스라 lunch/transit 간 충돌 없음.
    immediate_send_inflight: set[int] = field(default_factory=set)
    # §D 도서관 F-14 상태머신용. redis_url 미설정 시 None 이며 library worker 는 skip.
    redis_client: "Redis | None" = None
