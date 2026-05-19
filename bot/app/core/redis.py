from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis, from_url


async def create_redis_client(url: str) -> Redis:
    client: Redis = from_url(url, decode_responses=True)
    # redis-py의 ping은 sync/async overload라 mypy가 union을 본다. 비동기 클라이언트라
    # 실제로는 Awaitable[bool]임이 보장되어 cast로 좁힌다.
    await cast(Awaitable[bool], client.ping())
    return client
