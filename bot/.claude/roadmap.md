# Bot Roadmap

봇 컨테이너는 아직 코드 0줄이다. 이 문서는 첫 PR을 시작할 때 어디서부터 진입할지를 안내한다.

마지막 갱신: 2026-05-18 (그린필드, `.gitkeep`만 존재).

## 진행 상황 스냅샷

- 코드: 0줄. `bot/.gitkeep`만 있음.
- 청사진: `CLAUDE.md` + `.claude/{architecture,code_style,security,testing}.md` + 본 문서.
- 백엔드 의존성: notifications/notification_history 테이블 + 인덱스 준비 완료(backend 마이그레이션 0004). `users.status` 가드 가능.
- 인터페이스 합의 대기: notification_history.payload JSONB 스키마, 환영 DM 발송 책임 이전 시점 — backend roadmap §E-1과 묶여 있음.

## §0. 부트스트랩 (3-PR 분량)

### 0-1. 프로젝트 셋업 (우선순위: 최상)
- `pyproject.toml` + `uv lock`. 의존성: `discord.py>=2.3`, `apscheduler>=3.10`, `sqlalchemy>=2.0`, `asyncpg`, `redis>=5.0`, `httpx`, `pydantic>=2`, `pydantic-settings`, `structlog`.
- dev: `pytest`, `pytest-asyncio`, `respx`, `time-machine`, `fakeredis`, `ruff`, `mypy`.
- `Dockerfile` (multi-stage, slim base), `docker-compose.test.yml`(`name: ku-helper-bot-test`, 포트 5434), `.env.example`.
- `ruff`·`mypy` 설정은 백엔드 `pyproject.toml` 그대로 복사.

### 0-2. 엔트리포인트 + lifespan (우선순위: 최상)
- `app/main.py`: discord.Client 인스턴스 + APScheduler + redis 풀 + asyncpg 풀 + httpx 클라이언트를 lifespan 함수에서 셋업/종료. 잡 0개로 정상 기동·종료 확인.
- `app/core/config.py`: `Settings` (`discord_bot_token: SecretStr`, `database_url`, `redis_url`, `subway_api_key: SecretStr`, `admin_discord_ids: list[int]` 등).
- `app/core/discord.py`: `DiscordBotClient` 스켈레톤 (`start()`만, send는 §A-1에서 채움).
- `app/core/logging.py`: structlog JSON 출력.

### 0-3. DB 모델 + 읽기 Repository (우선순위: 최상)
- `app/db/models.py`: 백엔드 `app/domains/users/models.py`·`app/domains/notifications/models.py`의 형상을 그대로 duplicate. 마이그레이션은 만들지 않는다.
- `app/notifications/repository.py`: `NotificationRepository.list_active_subscriptions(type_: NotificationType, now: datetime) -> list[Notification]`. JOIN으로 `users.status = 'ACTIVE'` 필터.
- 통합 테스트 1개: 백엔드가 만든 스키마에 봇 모델이 호환되는지 확인 (alembic upgrade 후 SELECT 1회).

## §A. 발송 인프라

### A-1. DiscordBotClient 래퍼 (우선순위: 상)
- `open_dm_channel(discord_id: int) -> int` (채널 ID 반환, 캐시 가능).
- `send_embed(channel_id: int, embed: discord.Embed) -> None`.
- 429 응답 시 `Retry-After` 헤더 준수 + 백오프, 최대 3회 재시도. 백엔드 `app/core/discord.py:DiscordBotClient` 패턴 참고.

### A-2. Sender 큐 워커 (우선순위: 상)
- `app/notifications/sender.py`: `asyncio.Queue[SendDmTask]` 1개 + 워커 코루틴 1개.
- 발송 후 `NotificationHistoryRepository.insert_result(notification_id, user_id, status, payload, failure_reason)` 호출.
- 발송 직전 `user.status == ACTIVE` 재검증(이중 가드).

### A-3. 발송 실패 재시도 (F-21, 우선순위: 상)
- 지수 백오프 1·2·4초, 최대 3회. 모든 시도 실패 시 history에 `FAILED` + `failure_reason`.
- 회귀 가드 테스트: 모킹한 discord 호출이 3회 실패 → history 1 row(FAILED) + 큐 비움.

## §B. 첫 알림 흐름 — 교통 (가장 단순한 단일 경로)

### B-1. Subway Crawler
- `app/crawlers/subway/client.py`: 서울 공공 API 호출 + Redis TTL 캐시(키 `subway:{station}:{line}`, TTL 30초).
- 응답을 `SubwayArrival` dataclass로 정규화. raw dict 반환 금지.

### B-2. Transit Worker
- `app/notifications/transit/worker.py`: 활성 구독 → Subway Crawler 결과와 비교 → `build_transit_embed` → Sender 큐 적재.

### B-3. APScheduler 잡 등록
- `app/scheduler/jobs.py`에 `run_transit_job` 등록. 크론(예: `*/1 * * * *`)은 설정 가능.

### B-4. F-08 혼잡도·지연 정보 (우선순위: 중)
- 임베드 필드에 혼잡도(여유/보통/혼잡) + 지연 사유·예상 지연 시간 포함.

## §C. 점심 알림

### C-1. Lunch Crawler
- `app/crawlers/lunch/client.py`: 학식 페이지 크롤링 + Redis 캐시.
- 크롤링 정책 준수: 최소 1초 간격, User-Agent 명시.

### C-2. 주변 음식점 추천 (F-09)
- 데이터 소스 결정 필요 — 정적 JSON(번들) vs 외부 API. backend roadmap §E-1 합의에 따라 결정.
- 결정 후: `app/crawlers/restaurants/` 추가 또는 봇 내 정적 데이터 로더.

### C-3. F-10 가격 필터, F-12 오늘의 추천
- 가격 필터는 worker 단계에서. 오늘의 추천 하이라이트는 이전 추천 이력을 어디서 읽을지(history `payload` 활용) 결정 필요.

## §D. 도서관 알림 + F-14 상태 기반 중복 방지

### D-1. Library Crawler
- `app/crawlers/library/client.py`: 좌석 페이지 크롤링 + 캐시. 30초 이내 갱신 필요(F-13 SLA).

### D-2. 상태 기반 중복 방지 (F-14, 우선순위: 상)
- Redis 키 `library_alert:{user_id}:{room_id}` ∈ {`above`, `below`}.
- 발송 조건: 직전 `above` & 현재 임계값 이하 → 발송 → `below` 갱신.
- 회복(임계값 위로) 시 → `above`로 갱신, 발송 안 함.
- TTL은 충분히 길게(예: 24시간) — 자정 리셋이 아니라 상태 머신.

### D-3. F-15 긴급 임베드
- 임계값보다 더 낮은 "긴급 임계값" 설정 시 임베드 색상 빨강 + title에 "긴급" 키워드.

## §E. F-22 관리자 알림

### E-1. 크롤러 실패 카운터
- Crawler 예외 발생 시 Redis `INCR crawler_fail:{source}` + `EXPIRE 300`(5분).
- 잡 함수의 except 블록에서 호출.

### E-2. 3회 연속 누적 시 관리자 DM
- 카운터 값 ≥ 3이면 `AdminAlertTask`를 Sender 큐에 적재.
- 동일 장애 중복 방지: `crawler_alert_cooldown:{source}` TTL 30분. 이 키가 있으면 알림 skip.

## §F. F-18 활성 시간대 (백엔드 결정 후)

- 저장 위치 결정 대기 (User 컬럼 vs notification config JSONB). backend roadmap §B-2.
- 봇 측 작업: Worker가 `list_active_subscriptions` 후 현재 시각이 활성 시간대 안인지 필터. 발송 결정 직전에 평가.

## §G. 운영

### G-1. 로그 출력
- structlog JSON 포매터. Docker 로그 드라이버 합의(CloudWatch vs stdout).

### G-2. Health check
- 옵션 1: 봇 프로세스 내 작은 HTTP 서버(`aiohttp` 의존성 추가).
- 옵션 2: `discord.Client.is_ready()` 기반 파일 터치(`/tmp/bot_ready`). Docker healthcheck가 파일 mtime 확인.
- 권장은 옵션 2(의존성 추가 없음).

### G-3. CI 워크플로
- GitHub Actions: `docker compose -f docker-compose.test.yml up -d` + `uv sync` + ruff + mypy + pytest --cov.
- 백엔드 D-3과 같은 PR로 묶어도 무방.

## 백엔드와의 인터페이스 합의 (의존성)

§B/§C/§D 진입 전 합의 필요:
1. `notification_history.payload` JSONB 스키마 (임베드 스냅샷 포맷). backend roadmap §E-1.
2. 환영 DM 발송 책임 이전 시점 — 현재 backend `app/domains/auth/service.py:maybe_send_welcome_dm` → 봇으로 이전할지, 백엔드가 계속 책임질지. §A 완료 후 결정.
3. F-22 관리자 알림 발송 책임 — 봇 단독 vs 백엔드와 분담.

## 권장 순서

**§0-1 → §0-2 → §0-3 → §A-1 → §A-2 → §A-3 → §B → §C → §D → §E → §F → §G**

§B(교통)는 외부 데이터 소스(서울 공공 API)가 가장 안정적이고 조건 평가도 단순해서 첫 알림 흐름으로 적합. §B로 큐·Sender·History 전체 경로를 검증한 다음 §C/§D를 진행한다.
