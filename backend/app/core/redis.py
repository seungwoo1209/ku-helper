from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis, from_url


async def create_redis_client(url: str) -> Redis:
    client: Redis = from_url(url, decode_responses=True)
    # redis-py 의 ping 은 sync/async overload 라 mypy 가 union 을 본다. 비동기
    # 클라이언트라 실제로는 Awaitable[bool] 임이 보장되어 cast 로 좁힌다.
    await cast(Awaitable[bool], client.ping())
    return client
