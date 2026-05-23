# CLAUDE.md

ku-helper 프로젝트의 디스코드 봇은 PostgreSQL에서 사용자 알림 설정을 폴링하여 APScheduler로 조건을 평가하고, asyncio.Queue를 거쳐 Discord DM 임베드를 발송한다. 백엔드 API 컨테이너와는 PostgreSQL·Redis를 매개로 간접 통신하며, 직접 HTTP 호출은 하지 않는다.

## Stack

- Python 3.12, discord.py 2.0+
- APScheduler 3.10+ (`AsyncIOScheduler`)
- SQLAlchemy 2.0 (async) + `asyncpg`
  - 권한 최소화: `notifications` SELECT + `notification_history` INSERT만 사용
- Redis (redis-py asyncio): 외부 API 캐시, 도서관 알림 상태 키, 관리자 알림 쿨다운
- HTTP 클라이언트: `httpx.AsyncClient` (공공 API용)
- 패키지 매니저: `uv`
- 테스트: `pytest`, `pytest-asyncio`, `respx`, `time-machine`, `fakeredis`
- 린트/포맷: `ruff`, 타입체크: `mypy --strict`
- 로깅: `structlog`

## Commands

```bash
uv sync                                              # 의존성 설치
uv run python -m app.main                            # 봇 기동 (개발)
uv run pytest                                        # 테스트
uv run ruff check . && uv run ruff format .          # 린트 + 포맷
uv run mypy app                                      # 타입 체크
```

## Structure

```
app/
├── main.py                  # 엔트리포인트, lifespan(discord.Client·scheduler·redis·db 풀)
├── core/                    # config, database, discord(봇 토큰 격리), redis, logging, exceptions
├── db/                      # models.py(백엔드 스키마 duplicate), session
├── crawlers/                # 외부 데이터 소스별 클라이언트
│   ├── subway/              # 서울 공공 API
│   ├── lunch/               # 학식 페이지 크롤링
│   └── library/             # 도서관 좌석 크롤링
├── notifications/           # 알림 종류별 worker + 공통 sender
│   ├── transit/             # worker.py, embeds.py
│   ├── lunch/
│   ├── library/
│   ├── sender.py            # asyncio.Queue 워커, history INSERT
│   └── history_repository.py
├── admin/                   # F-22 관리자 DM 알림
└── scheduler/               # APScheduler 잡 등록(jobs.py)
tests/                       # app/ 구조 미러링
```

새 알림 종류를 추가할 때는 `app/crawlers/<source>/`와 `app/notifications/<type>/`를 함께 만든다.

## Rules

1. 호출 순서는 **Scheduler → Worker → Crawler/Repository → Sender**. 계층 건너뛰기 금지.
2. 모든 I/O는 `async`. discord.py·asyncpg·redis-py·httpx 동기 호출 금지. `time.sleep`, `requests` 금지.
3. Discord 봇 토큰은 `Settings.discord_bot_token: SecretStr`로만 받고, `app/core/discord.py`의 `DiscordBotClient` 외부로 노출하지 않는다.
4. ORM 모델은 백엔드와 **별도로 정의**한다(`app/db/models.py`). 봇은 alembic을 실행하지 않으며 스키마 변경 권한이 없다.
5. `notification_history` INSERT는 Sender 워커만 수행한다. UPDATE/DELETE 호출은 코드에 두지 않는다(백엔드 cascade 책임).
6. Discord API rate limit과 `429` 백오프는 `app/core/discord.py`에서 처리한다. 상위 계층(Worker/Sender)은 모른다.
7. 설정은 `app/core/config.py`의 `Settings`만을 통해 접근한다. `os.environ` 직접 사용 금지.

## Detail rules

@.claude/architecture.md
@.claude/testing.md
@.claude/code_style.md
@.claude/security.md

## Roadmap

봇 컨테이너는 아직 코드 0줄이다. 다음 PR을 시작할 때는 잔여 작업·정책 미결 사항·우선순위를 먼저 확인한다.

@ROADMAP.md
