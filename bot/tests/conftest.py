import os

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
