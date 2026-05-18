import os

# app.core.database 가 import 시점에 get_settings() 를 호출해 engine 을 만든다.
# 테스트에서 실제 DB/Discord 에 붙지 않더라도 Settings 검증을 통과시켜야 import 가 가능.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)
os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
