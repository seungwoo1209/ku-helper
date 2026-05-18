# CLAUDE.md

ku-helper 프로젝트의 API 서버는 디스코드 OAuth 로그인(사용자 설치, `integration_type=1`)을 수행하고, 클라이언트의 알림 설정을 받아 데이터베이스에 알림 내용을 저장하는 백엔드다.

## Stack

- Python 3.12, FastAPI 0.115+
- SQLAlchemy 2.0 (async) + `asyncpg`
- PostgreSQL 16, Alembic
- 패키지 매니저: `uv`
- 테스트: `pytest`, `pytest-asyncio`, `httpx.AsyncClient`
- 린트/포맷: `ruff`, 타입체크: `mypy --strict`
- 인증: `PyJWT`, 로깅: `structlog`

## Commands

```bash
uv sync                                              # 의존성 설치
uv run uvicorn app.main:app --reload                 # 개발 서버
uv run pytest                                        # 테스트
uv run ruff check . && uv run ruff format .          # 린트 + 포맷
uv run mypy app                                      # 타입 체크
uv run alembic upgrade head                          # 마이그레이션 적용
uv run alembic revision --autogenerate -m "<msg>"    # 마이그레이션 생성
```

## Structure

```
app/
├── main.py            # FastAPI 인스턴스, 라이프스팬, 미들웨어
├── core/              # config, database, security, logging, exceptions
├── domains/<name>/    # router, service, repository, models, schemas, exceptions
└── api/v1/            # v1 라우터 집계
tests/                 # app/ 구조 미러링
alembic/versions/      # 마이그레이션 파일
```

새 도메인을 추가할 때는 `app/domains/<name>/`에 `router.py`, `service.py`, `repository.py`, `models.py`, `schemas.py`, `exceptions.py` 6개 파일을 생성한다. 비어 있어도 만든다.

## Rules

- 호출 순서는 Router → Service → Repository. 계층을 건너뛰지 않는다.
- 모든 의존성 주입은 `Annotated[T, Depends(...)]` 문법을 쓴다. 구식 `T = Depends(...)`는 금지.
- Service는 `fastapi`, `starlette`에서 어떤 것도 import하지 않는다. 도메인 예외를 던지면 `main.py`의 핸들러가 HTTP 응답으로 변환한다.
- 동기 DB 드라이버, `requests`, `time.sleep` 금지. 모든 I/O는 `async`.
- Pydantic 스키마는 입력(`*Create`, `*Update`)과 출력(`*Read`)을 분리한다. ORM 모델을 응답으로 직접 반환하지 않는다.
- 설정은 `app/core/config.py`의 `Settings`만을 통해 접근한다. `os.environ` 직접 사용 금지.
- 모델 변경 PR에는 Alembic 마이그레이션을 포함한다. `autogenerate` 결과는 사람이 검토한 뒤 커밋한다.

## Detail rules

@.claude/architecture.md
@.claude/testing.md
@.claude/code_style.md
@.claude/security.md

## Roadmap

다음 백엔드 PR을 시작할 때는 잔여 작업·정책 미결 사항·잠재 부채를 먼저 확인한다.

@.claude/roadmap.md