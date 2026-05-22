import os

import fakeredis.aioredis
import pytest

# app.core.database 가 import 시점에 get_settings() 를 호출해 engine 을 만든다.
# 테스트에서 실제 DB/Discord 에 붙지 않더라도 Settings 검증을 통과시켜야 import 가 가능.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)
os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
# F-07 SubwayClient 생성자가 subway_api_key 빈값이면 즉시 SubwayApiAuthFailed 를 raise.
# 테스트에서는 유효 키 형식이기만 하면 되므로 더미 값을 사용한다.
os.environ.setdefault("SUBWAY_API_KEY", "test-subway-key")
# ADMIN_DISCORD_IDS 가 빈 문자열이면 list[int] 파싱이 실패하므로 빈 JSON 배열로 설정.
os.environ.setdefault("ADMIN_DISCORD_IDS", "[]")
# redis_url 은 필수(Settings). 테스트에서는 더미 URL 로 Settings 검증만 통과시키면 되고
# 실제 Redis 연결은 fakeredis 픽스처가 대체한다.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture
def redis_client() -> fakeredis.aioredis.FakeRedis:
    """fakeredis 기반 Redis 클라이언트. 각 테스트마다 독립 인스턴스를 반환한다."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)
