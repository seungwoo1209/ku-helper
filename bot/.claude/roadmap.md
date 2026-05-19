# Bot Roadmap

다음 봇 PR을 시작할 때 잔여 작업·정책 미결 사항·우선순위를 먼저 확인한다.

마지막 갱신: 2026-05-19 (F-07 교통 정기 알림 종단 PR 완료, 다음은 §A-3 또는 F-06).

## 진행 상황 스냅샷

완료된 마일스톤 (브랜치 `feat/bot`):
- §0 부트스트랩: 코어(`config`, `database`, `discord`, `logging`, `redis`, `exceptions`), DB 모델(`User`/`Notification`/`NotificationHistory`), `NotificationRepository` (`list_active_subscriptions`, `get_user_status`).
- 스케줄러 골격(커밋 `d189b32`): `register_jobs` 가 알림 타입별 정적 폴링 잡 3종 등록 — TRANSIT/LIBRARY 5초, LUNCH 60초, `IntervalTrigger`+`max_instances=1`+`coalesce`+`misfire_grace_time=5`. 워커는 활성 구독 SELECT 후 count 로그만 — 조건 평가는 §B/§C/§D 에서.
- §A-1 `DiscordBotClient.send_embed` (커밋 `c09030e`): `fetch_user → create_dm → channel.send`. `discord.HTTPException` 그대로 전파. `wait_until_ready()` 위임 메서드 포함.
- §A-2 Sender 큐·워커 (커밋 `c09030e`): `asyncio.Queue[SendDmTask]` + 단일 워커. 이중 가드(ACTIVE 재검증) → DM → SUCCESS/FAILED history INSERT. 1 task = 1 트랜잭션. 회귀 가드 5건.
- 테스트: 12 passing (`tests/scheduler/test_jobs.py` 3, `tests/core/test_discord.py` 3, `tests/notifications/test_sender.py` 6).
- 도구: `bot-coder` 서브에이전트가 레포 루트 `.claude/agents/` 에 정의됨. 본 도메인 작업은 메인 세션이 위임.
- F-07 교통 정기 알림 종단 (현재 PR): `SubwayClient` + `transit/worker.py` + `transit/embeds.py` + `JobContext` + lifespan httpx 클라이언트 + in-flight set. DB → 워커 → 큐 → DM 의 첫 실제 발송 검증.

인터페이스 합의 대기 (백엔드 결정 필요):
- `notification_history.payload` JSONB 스키마 — backend roadmap §E-1. 현재는 임시 dict 로 INSERT 중.
- 환영 DM 발송 책임 이전 시점 — 현재 backend `auth/service.py:maybe_send_welcome_dm` 보유. §A 종료 후 재논의.
- F-22 관리자 알림 분담(봇 단독 vs 백엔드 분담) — 미정.

알려진 부채:
- `Dockerfile` / `docker-compose.test.yml` 미작성 — §0-1 잔여. 현재 로컬 `uv run` 으로만 실행. G-3 CI 이전에 필요.
- alembic 호환성 통합 테스트 1건 미작성 — §0-3 잔여. 백엔드가 만든 스키마 변경이 봇 모델과 어긋나는 회귀를 잡지 못함.
- DM 채널 캐시 미구현 — 매 발송 `fetch_user + create_dm`. 부하 측정 후 별도 PR.
- §A-1 의 명시적 429 Retry-After/재시도는 §A-3 로 이관. 현재는 discord.py 내장 핸들러에만 의존.
- Sender 워커가 `discord.DiscordException` 하위 전체를 동일 FAILED 로 처리 — `Forbidden`/`NotFound` 분기는 요구 시 추가.
- F-07 발송 중복 방지가 메모리 set 의존 — 봇 재기동 시 첫 틱에서 history 가드만으로 보호. Redis 도입(§C-1) 시 분산 가능.
- SubwayClient 가 Redis 캐시 없이 매 5초 틱마다 외부 API 호출. 같은 station 의 구독은 한 틱 내 dict 캐시로 호출 1회로 합쳐짐. 본격 부하 시 Redis TTL 캐시(§C-1) 도입.

## §0. 부트스트랩 (3-PR 분량)

### 0-1. 프로젝트 셋업 (우선순위: 최상) — 부분 완료
- `pyproject.toml` + `uv.lock` + `.env.example`: 완료. 의존성 + dev 도구 + ruff/mypy 설정 적용.
- `Dockerfile` (multi-stage, slim base), `docker-compose.test.yml`(`name: ku-helper-bot-test`, 포트 5434): **미작성**. §G-3 CI 진입 전에 작성.

### 0-2. 엔트리포인트 + lifespan (우선순위: 최상) — 완료
- `app/main.py`: discord.Client + APScheduler + redis(옵셔널) + asyncpg + Sender 큐·워커 셋업/종료.
- `app/core/{config,discord,logging,redis,exceptions,database}.py`: 모두 작성됨.
- httpx 클라이언트 lifespan 합류는 §B(Subway Crawler) 진입 시 추가.

### 0-3. DB 모델 + 읽기 Repository (우선순위: 최상) — 부분 완료
- `app/db/models.py`: `User`/`Notification`/`NotificationHistory` + enum 3종 작성됨.
- `app/notifications/repository.py`: `list_active_subscriptions(type_)` + `get_user_status(user_id)`. (현재 시그니처는 `now` 인자 없이 호출 — 시간 의존 평가는 worker 가 담당하도록 위임.)
- alembic 호환성 통합 테스트 1건: **미작성**. 일반 `pytest` 는 `Base.metadata.create_all` 사용 → 백엔드 마이그레이션 회귀를 못 잡음. §G-3 CI 와 묶어 보강 권장.

## §A. 발송 인프라

### A-1. DiscordBotClient 래퍼 (우선순위: 상) — 완료 (커밋 `c09030e`)
- `open_dm_channel(discord_id) -> discord.DMChannel`, `send_embed(discord_id, embed) -> None`, `wait_until_ready()` 위임 메서드.
- `discord.HTTPException` 은 그대로 위로 전파 — Sender 가 catch 해 FAILED INSERT.
- 명시적 Retry-After 백오프·3회 재시도는 §A-3 로 이관 — 현재는 discord.py 내장 핸들러에만 의존.
- DM 채널 캐시 미구현 — 매 발송 `fetch_user + create_dm`. 부하 측정 후 별도 PR.

### A-2. Sender 큐 워커 (우선순위: 상) — 완료 (커밋 `c09030e`)
- `app/notifications/sender.py`: `SendDmTask` (frozen dataclass, `notification_id: int | None` 로 F-22 공유 큐 대비) + `run_sender_worker`.
- 1 task = 1 트랜잭션. `NotificationHistoryRepository.insert_result` 가 flush, Sender 가 commit.
- 이중 가드: 큐에서 꺼낸 시점에 `get_user_status` 재검증. DELETED 또는 사용자 행 없음이면 FAILED + `user_deleted`.
- Worker → 큐 적재는 §B 부터 — 본 시점에는 큐가 비어 있고 워커 task 만 살아 있다.

### A-3. 발송 실패 재시도 (F-21, 우선순위: 상) — **다음 PR**
- 지수 백오프 1·2·4초, 최대 3회. 모든 시도 실패 시 history에 `FAILED` + `failure_reason`.
- 회귀 가드 테스트: 모킹한 discord 호출이 3회 실패 → history 1 row(FAILED) + 큐 비움.
- 구현 위치: `_process_task` 의 `discord.DiscordException` catch 자리에 retry 루프. INSERT 는 마지막 한 번만 (시도마다 INSERT 하지 않음).

## §B. 첫 알림 흐름 — 교통 (가장 단순한 단일 경로)

### B-1. Subway Crawler
- `app/crawlers/subway/client.py`: 서울 공공 API 호출 + Redis TTL 캐시(키 `subway:{station}:{line}`, TTL 30초).
- 응답을 `SubwayArrival` dataclass로 정규화. raw dict 반환 금지.
**완료(현재 PR, Redis 캐시 미적용 — §C-1 도입 후 추가).**

### B-2. Transit Worker
- `app/notifications/transit/worker.py`: 활성 구독 → Subway Crawler 결과와 비교 → `build_transit_embed` → Sender 큐 적재.
**완료(현재 PR, F-07 만). F-06 (arrival) 은 후속 PR.**

### B-3. APScheduler 잡 등록 — 부분 완료 (커밋 `d189b32`)
- `register_jobs` 가 `run_transit_job`/`run_lunch_job`/`run_library_job` 을 이미 등록 — TRANSIT/LIBRARY 5초, LUNCH 60초 `IntervalTrigger`. 잡 옵션 `max_instances=1`, `coalesce=True`, `misfire_grace_time=5`.
- 현재 worker 본체는 활성 구독 SELECT + count 로그만. Subway Crawler/조건 평가/임베드/큐 적재는 §B-1·§B-2 에서 채운다.
- 이제 transit 잡이 실제로 SubwayClient 호출 + 큐 적재
- 틱 주기 조정 가능 — TRANSIT/LIBRARY 부하 측정 후 5→10초 등 완화 검토.

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

**§0 → §A-1 → §A-2 → §B(F-07) (완료) → §A-3 → §B(F-06) → §C/§D → §E → §F → §G**

§B(교통)는 외부 데이터 소스(서울 공공 API)가 가장 안정적이고 조건 평가도 단순해서 첫 알림 흐름으로 적합. §B 로 큐·Sender·History 전체 경로를 검증한 다음 §C/§D 를 진행한다.

병행 가능 항목 (§A-3 와 충돌하지 않음):
- §0-1 잔여: `Dockerfile` / `docker-compose.test.yml` — §G-3 CI 와 같은 PR로 묶어도 무방.
- §0-3 잔여: alembic 호환성 통합 테스트 1건.
