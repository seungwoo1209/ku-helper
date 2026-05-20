# Bot Roadmap

다음 봇 PR을 시작할 때 잔여 작업·정책 미결 사항·우선순위를 먼저 확인한다.

마지막 갱신: 2026-05-21 — LIBRARY 종단 완료. 스케줄 알림(F-13 임계값 / F-14 Redis 상태머신 중복방지 / F-15 긴급) + 즉시 발송(`POST /api/v1/me/immediate-send/library` ↔ `run_immediate_send_library_job`) 양쪽 가동. 이로써 TRANSIT/LUNCH/LIBRARY 3종 즉시 발송 + 교통(F-07)·도서관 정기 알림 운영. **Redis 가 F-14 용으로 신규 도입**(`JobContext.redis_client` 배선). §D 완료.

## 진행 상황 스냅샷

완료된 마일스톤 (브랜치 `feat/bot`):
- §0 부트스트랩: 코어(`config`, `database`, `discord`, `logging`, `redis`, `exceptions`), DB 모델(`User`/`Notification`/`NotificationHistory`), `NotificationRepository` (`list_active_subscriptions`, `get_user_status`).
- 스케줄러 골격(커밋 `d189b32`): `register_jobs` 가 알림 타입별 정적 폴링 잡 3종 등록 — TRANSIT/LIBRARY 5초, LUNCH 60초, `IntervalTrigger`+`max_instances=1`+`coalesce`+`misfire_grace_time=5`. 워커는 활성 구독 SELECT 후 count 로그만 — 조건 평가는 §B/§C/§D 에서.
- §A-1 `DiscordBotClient.send_embed` (커밋 `c09030e`): `fetch_user → create_dm → channel.send`. `discord.HTTPException` 그대로 전파. `wait_until_ready()` 위임 메서드 포함.
- §A-2 Sender 큐·워커 (커밋 `c09030e`): `asyncio.Queue[SendDmTask]` + 단일 워커. 이중 가드(ACTIVE 재검증) → DM → SUCCESS/FAILED history INSERT. 1 task = 1 트랜잭션. 회귀 가드 5건.
- 도구: `bot-coder` 서브에이전트가 레포 루트 `.claude/agents/` 에 정의됨. 본 도메인 작업은 메인 세션이 위임.
- F-07 교통 정기 알림 종단 (커밋 `6703ded`): `SubwayClient` + `transit/worker.py` + `transit/embeds.py` + `JobContext` + lifespan httpx 클라이언트 + in-flight set. DB → 워커 → 큐 → DM 경로 구축.
- 서울 지하철 API 참고 문서 (커밋 `bb35e19`): `bot/docs/seoul_subway_realtime_arrival_api.md`. SubwayClient 의 필드 매핑·에러 코드·`subwayId` 호선 코드 1차 소스.
- worker 버그 2건 수정 (커밋 `18668ce`): (1) `cfg.get("interval_minutes")` → `repeat_interval_minutes` 키 교정 — 기존엔 interval 가드가 비활성화돼 매 틱 재발송 위험. (2) UTC 문자열 사전식 비교 → KST `datetime.time` 객체 비교 (`zoneinfo.ZoneInfo("Asia/Seoul")` + `_parse_config_time` helper). 회귀 가드 2건 추가.
- 실 DM 1건 발송 검증 (2026-05-19 18:24 KST): user_id=1 (`dogbugbaby`) 강남역 2호선 F-07 구독 → `transit_queued` → `dm_sent` → `notification_history` SUCCESS row 1건. 임베드 4 필드(내선/외선 각 2건).
- §A-3 발송 실패 재시도 (F-21) 완료 (커밋 미정): `RETRY_BACKOFF_SECONDS=(1.0, 2.0)` + `_MAX_ATTEMPTS=3`. `_process_task` 에 retry 루프 추가. INSERT 마지막 1회만. `dm_send_retry`/`dm_failed`/`dm_sent` 로그 키 유지. 회귀 가드 4건 추가.
- TRANSIT 즉시 발송 종단 (커밋 미정): `ImmediateSendTransitRepository.list_pending` (LEFT JOIN 가드 + ACTIVE 필터 + type=TRANSIT) + `run_immediate_send_transit_job` (lunch 즉시 발송 워커 패턴 미러, SubwayClient 호출 + `build_transit_recurring_embed` 재사용) + `immediate_send_transit_poll` 잡 등록 (5초 인터벌). `lunch_inflight` → `immediate_send_inflight` 로 일반화하여 lunch + transit 즉시 발송 워커가 단일 in-flight 셋을 공유 (request_id 단일 시퀀스라 충돌 없음).
- 테스트: **60 passing** (이전 37 + 즉시 발송 transit 회귀 가드 23: worker 4 + repository 4 + scheduler 1 + 기존 jobs/worker 케이스 확장 14). 신규 파일: `tests/notifications/transit/test_repository.py`.
- origin/main 머지 (커밋 `e9ddc7f`): frontend 대시보드 + backend `routes/lunch.py` 부채 경로 + `bot/scrapers/` 부채 경로 유입. 백엔드 D-4 부채는 폐기 완료 (backend `routes/`, `data/` 삭제 + `bot/scrapers/` 삭제). 봇 측 D-5 도 정식 채널로 승격 — 알려진 부채 절 참고.
- LIBRARY 스케줄 알림 종단 (커밋 `5691741`): `LibraryClient`(crawler — name 정규식 `제\s*(\d+)\s*열람실` 파싱 → 번호별 available/total 합산, 0=전체, 모듈 TTL 캐시 15s) + `library/embeds.py`(`build_library_embed`, F-15 긴급 빨강/키워드) + `library/worker.py:run_library_job`(F-13 임계값 평가 + F-14 Redis 상태머신 `library_alert:{user_id}:{room_id}` ∈ above/below, TTL 24h, 발송=큐 적재 시점에 below 갱신). **Redis 신규 도입** — `JobContext.redis_client` 배선(`main.py`), redis_url 미설정 시 잡 skip. `Settings.library_seat_url` + dev 의존성 `fakeredis` 추가. 백엔드 `LibraryConfig.reading_room_id` 는 논리 열람실 번호 Literal[0,1,2,3,5](0=전체 합산, 4 미운영) — A/B 분리·전체 합산은 봇 크롤러가 처리.
- LIBRARY 즉시 발송 종단 (커밋 `4f89342`): `run_immediate_send_library_job` (lunch/transit 즉시발송 패턴 미러) + `build_library_immediate_embed`(현재 잔여/총만, 임계값·긴급 없음) + `immediate_send_library_poll` 잡(5초). crawler 실패·열람실 부재 시 워커 직접 FAILED INSERT(아키텍처 예외). Redis 미사용(즉시발송엔 상태머신 없음). 백엔드 `POST /api/v1/me/immediate-send/library` 와 짝.
- 테스트: **84 passing** (이전 60 + LIBRARY 스케줄 가드 19[crawler 8 + worker 7 + embeds 4] + 즉시발송 LIBRARY 5[worker 4 + scheduler 1]). 신규 디렉터리: `tests/crawlers/library/`, `tests/notifications/library/`.

인터페이스 합의 대기 (백엔드 결정 필요):
- `notification_history.payload` JSONB 스키마 — backend roadmap §E-1. 현재는 임시 dict 로 INSERT 중.
- 환영 DM 발송 책임 이전 시점 — 현재 backend `auth/service.py:maybe_send_welcome_dm` 보유. §A 종료 후 재논의.
- F-22 관리자 알림 분담(봇 단독 vs 백엔드 분담) — 미정.

알려진 부채:
- **Redis 부분 도입 (2026-05-21)**: F-14 도서관 상태머신용으로 `JobContext.redis_client` + lifespan 연결이 추가됨. 단 subway/lunch/restaurants 크롤 캐시는 여전히 모듈 dict 만 사용 — 이들 Redis TTL 캐시 이전·E(F-22) 카운터 등은 후속(§C-1 잔여). 즉시발송 잡은 Redis 미사용.
- `Dockerfile` / `docker-compose.test.yml` 미작성 — §0-1 잔여. 현재 로컬 `uv run` 으로만 실행. G-3 CI 이전에 필요. Redis 도입으로 dev/test compose 에 redis 서비스도 함께 필요.
- alembic 호환성 통합 테스트 1건 미작성 — §0-3 잔여. 백엔드가 만든 스키마 변경이 봇 모델과 어긋나는 회귀를 잡지 못함.
- DM 채널 캐시 미구현 — 매 발송 `fetch_user + create_dm`. 부하 측정 후 별도 PR.
- §A-1 의 명시적 429 Retry-After/재시도는 §A-3 로 이관. 현재는 discord.py 내장 핸들러에만 의존.
- Sender 워커가 `discord.DiscordException` 하위 전체를 동일 FAILED 로 처리 — `Forbidden`/`NotFound` 분기는 요구 시 추가.
- F-07 발송 중복 방지가 메모리 set 의존 — 봇 재기동 시 첫 틱에서 history 가드만으로 보호. Redis 도입(§C-1) 시 분산 가능.
- SubwayClient 가 Redis 캐시 없이 매 5초 틱마다 외부 API 호출. 같은 station 의 구독은 한 틱 내 dict 캐시로 호출 1회로 합쳐짐. 본격 부하 시 Redis TTL 캐시(§C-1) 도입.
- 봇이 `notification.config` 를 raw `dict` 로 읽음 — Pydantic 검증 없음. 백엔드 스키마 키 이름 변경이 워커에서 silently fail 가능 (실제로 `repeat_interval_minutes` ↔ `interval_minutes` 회귀 발생). 후속 정리: `app/notifications/transit/config_parsers.py` 같은 봇 측 Pydantic 모델 도입 또는 backend 와 schema 공유 패키지.
- transit 윈도우 비교가 KST 고정 (`zoneinfo.ZoneInfo("Asia/Seoul")`). 다국가 확장 시 사용자별 timezone 컬럼 필요 — 현재 단일 캠퍼스 한정이라 보류.
- 학식 크롤러가 Playwright 의존 — 봇 컨테이너 이미지 크기 ↑. 추후 부하 측정 후 별도 컨테이너로 분리 검토.
- 즉시 발송 dedupe 는 `notification_history.immediate_send_request_id` FK 의존 — 봇은 SELECT 만, UPDATE 권한 없음. 백엔드 roadmap §D-5 (정식 on-demand 채널) 와 같은 라이프사이클.
- 즉시 발송 lunch/transit 워커가 `ImmediateSendRequestRow` dataclass 를 `bot/app/notifications/lunch/repository.py` 에서 공유한다. 알림 종류별 payload 검증이 필요해지는 시점에 `app/notifications/repository.py` 또는 `app/notifications/immediate_send/` 공통 모듈로 이전한다. 현재는 LIBRARY 즉시 발송 추가 시 같은 패턴을 따르면 충분.
- `immediate_send_inflight` 메모리 셋 — 봇 재기동 시 비워진다. 같은 request_id 가 두 번 처리되는 회귀는 `notification_history.immediate_send_request_id` partial unique 인덱스 + LEFT JOIN 가드로 INSERT 단계에서 막힌다 (DM 자체가 두 번 발송될 가능성은 거의 없음 — 5초 폴링 간격 내 재기동만 위험).
- Lunch/Restaurants 크롤러가 Redis 캐시 없이 모듈 dict 캐시만 사용. 봇 재기동 시 첫 요청에서 재크롤링. §C-1 정식 일정에 Redis 캐시 추가.
- **아키텍처 예외: Lunch worker 직접 FAILED INSERT** — `app/notifications/lunch/worker.py` 의 crawler 실패 분기에서 워커가 `NotificationHistoryRepository.insert_result` 를 직접 호출한다. `CLAUDE.md` rule 5 ("Sender 만 INSERT") + architecture.md Worker 절을 우회. 이유: crawler 가 실패하면 embed/payload 를 만들 수 없어 Sender 큐에 넣을 task 자체가 없는데, history row 가 없으면 `list_pending` 의 LEFT JOIN 가드가 풀리지 않아 매 5초 재시도된다. 정식 정리 후보: `SendDmTask` 에 "이미 실패 확정" 플래그를 두고 Sender 가 그 케이스에선 send 호출을 건너뛰고 history INSERT 만 수행하도록 통합. transit worker 의 SubwayClient 실패 분기도 같은 패턴을 갖게 되면 함께 리팩터.

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

### A-3. 발송 실패 재시도 (F-21, 우선순위: 상) — 완료 (커밋 미정)
- 지수 백오프 1·2·4초(`RETRY_BACKOFF_SECONDS=(1.0, 2.0)`, `_MAX_ATTEMPTS=3`), 최대 3회. 모든 시도 실패 시 history에 `FAILED` + `failure_reason`.
- 회귀 가드 테스트 4건: (1) 3회 실패 → FAILED 1 row + send 3회, (2) 2회 실패 후 성공 → SUCCESS 1 row + send 3회, (3) 1회 성공 → sleep 0회, (4) 백오프 sleep 인자 1.0·2.0 검증.
- 구현 위치: `_process_task` 의 `discord.DiscordException` catch 자리에 retry 루프. INSERT 는 마지막 한 번만.

## §B. 첫 알림 흐름 — 교통 (가장 단순한 단일 경로)

### B-1. Subway Crawler — 완료 (커밋 `6703ded`)
- `app/crawlers/subway/client.py`: 서울 공공 API 호출. 응답을 `SubwayArrival` dataclass로 정규화. raw dict 반환 금지.
- Redis TTL 캐시(키 `subway:{station}:{line}`, TTL 30초)는 **미적용** — §C-1 Redis 도입 후 추가.
- API 키는 `Settings.subway_api_key: SecretStr` 로 격리. URL 로그 출력 시 마스킹.

### B-2. Transit Worker — 완료 (커밋 `6703ded` + 버그 수정 `18668ce`)
- `app/notifications/transit/worker.py`: 활성 구독 → SubwayClient 결과 → `build_transit_recurring_embed` → Sender 큐 적재.
- 현재 **F-07 (recurring) 만** 구현. F-06 (arrival) 은 후속 PR.
- 윈도우 비교 KST 고정 (`Asia/Seoul`). interval 가드는 history 마지막 SUCCESS row + 메모리 in-flight set 이중.

### B-3. APScheduler 잡 등록 — 완료 (커밋 `d189b32` + `6703ded`)
- `register_jobs` 가 `run_transit_job`/`run_lunch_job`/`run_library_job` 을 모두 등록 — TRANSIT/LIBRARY 5초, LUNCH 60초 `IntervalTrigger`. 잡 옵션 `max_instances=1`, `coalesce=True`, `misfire_grace_time=5`.
- transit 잡은 `JobContext` 를 `args=[ctx]` 로 받아 SubwayClient 호출 + 큐 적재까지 실 수행.
- lunch 정기 잡은 여전히 stub (활성 구독 count 로그만, §C-4 후속). library 정기 잡은 본체 구현 완료(§D, 커밋 `5691741`). immediate_send lunch/transit/library 잡 3종도 등록됨.
- 틱 주기 조정 가능 — TRANSIT/LIBRARY 부하 측정 후 5→10초 등 완화 검토.

### B-4. F-08 혼잡도·지연 정보 (우선순위: 중)
- 임베드 필드에 혼잡도(여유/보통/혼잡) + 지연 사유·예상 지연 시간 포함.

## §C. 점심 알림 — 즉시 발송 종단 우선

### C-1. 정식 Lunch Crawler — 진행 중
- `app/crawlers/lunch/client.py`: 건국대 학식 페이지 Playwright 크롤링. `LunchMenu`/`LunchCorner` dataclass 반환. 모듈 dict 캐시(ISO 주 단위, asyncio.Lock 가드).
- lifespan 에서 단일 `playwright`+`chromium Browser` 인스턴스 생성·재사용. 매 호출은 새 context 만 생성·종료.
- 도메인 예외: `LunchCrawlerFailed` (selector 미일치·timeout 등). raw httpx/Playwright 예외 위로 흘리지 않음.
- 데이터 소스 URL·selector 는 `app/crawlers/lunch/client.py` 구현 참고 (이전 부채 경로 `bot/scrapers/cafeteria.py` 는 삭제됨 — git 히스토리에서 확인 가능).
- Redis TTL 캐시는 후속 (Redis 도입 시 키 `lunch:cafeteria:{iso_week}` TTL 7일).

### C-2. 정식 Restaurants Crawler — 진행 중
- `app/crawlers/restaurants/client.py`: Naver Local Search API. `Restaurant` dataclass 반환. 카테고리 10건 × 5건 → dedup → 풀.
- 키 격리: `Settings.naver_search_client_id: str`, `Settings.naver_search_client_secret: SecretStr`.
- 모듈 dict 캐시(날짜 단위). Redis TTL 캐시는 후속.
- 도메인 예외: `RestaurantsCrawlerFailed` (HTTP 4xx/5xx).
- `_QUERIES`·`_normalize`·HTML entity 정제 로직은 git 히스토리의 `bot/scrapers/restaurants.py` (삭제된 부채 경로) 에서 확인 가능. dataclass 래핑·structlog 추가·`Settings` 키 사용으로 재작성.

### C-3. 즉시 발송 Lunch Worker — 진행 중
- `app/notifications/lunch/worker.py:run_immediate_send_lunch_job`: 5초 간격 폴링. `immediate_send_requests` (type=LUNCH, status=ACTIVE 사용자, history join 으로 미발송) 픽업.
- 각 row 별 `asyncio.gather(LunchClient.fetch_today_menu(), RestaurantsClient.fetch_pool())` 병렬 호출 → `random.sample(pool, 3)` → `build_lunch_immediate_embed` → Sender 큐 적재.
- in-flight set 으로 같은 틱 중복 적재 방지. history INSERT 후 sender 가 set 에서 discard. transit F-07 패턴 재사용.
- `SendDmTask` 에 `immediate_send_request_id` 필드 추가. `notification_id` 와 mutually exclusive.

### C-4. F-10 가격 필터, F-12 오늘의 추천 — 후속
- 가격 필터는 worker 단계에서. 오늘의 추천 하이라이트는 이전 추천 이력을 어디서 읽을지(history `payload` 활용) 결정 필요.
- 정식 알림 시스템(스케줄 기반) 도입 시 다룬다. 현재 즉시 발송 종단만 우선.

## §D. 도서관 알림 + F-14 상태 기반 중복 방지 — 완료 (커밋 `5691741`, 즉시발송 `4f89342`)

### D-1. Library Crawler — 완료
- `app/crawlers/library/client.py`: 좌석 API(JSON) GET → name 정규식 파싱으로 논리 번호별 합산. `RoomSeats` dataclass 반환. 모듈 TTL 캐시(15s, asyncio.Lock). `Settings.library_seat_url` 미설정 시 `LibraryCrawlerFailed`. Redis TTL 캐시는 후속(§C-1).

### D-2. 상태 기반 중복 방지 (F-14) — 완료
- Redis 키 `library_alert:{user_id}:{room_id}` ∈ {`above`, `below`}, TTL 24h.
- 직전 `above` & 현재 임계값 이하 → 발송 + `below` 갱신(워커가 큐 적재 시점에). 회복 시 `above`. 키 미존재 시 `above` 기본값.
- `redis_client` 미설정 환경에선 잡 skip(warn 로그). 회귀 가드: below→below 재발송 안 함.

### D-3. F-15 긴급 임베드 — 완료
- `urgent_threshold` 이하면 `build_library_embed` 가 색상 빨강 + title "🚨 [긴급]". `urgent_threshold` null 이면 긴급 표시 안 함.

### D-4. LIBRARY 즉시 발송 — 완료 (커밋 `4f89342`)
- `run_immediate_send_library_job` + `build_library_immediate_embed`(현재 좌석만). `immediate_send_library_poll` 5초 잡. 백엔드 `POST /me/immediate-send/library` 와 짝. crawler 실패·방 부재 시 워커 직접 FAILED INSERT.

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

**§0 → §A-1 → §A-2 → §B(F-07) (완료) → §A-3 (완료) → §C-1·C-2·C-3 lunch 즉시 발송 (완료) → TRANSIT 즉시 발송 (완료) → §D (완료, LIBRARY 정기+즉시발송) → §B(F-06) → §C-4 → §E → §F → §G**

남은 우선 작업: §E(F-22 관리자 알림), §B-4(F-08 혼잡도), §C-4(가격 필터·오늘의 추천), §F(F-18 활성 시간대, 백엔드 합의 후), §G(Dockerfile·CI·health check), subway/lunch Redis 캐시 이전.

§B(교통)는 외부 데이터 소스(서울 공공 API)가 가장 안정적이고 조건 평가도 단순해서 첫 알림 흐름으로 적합. §B 로 큐·Sender·History 전체 경로를 검증한 다음 §C/§D 를 진행한다.

병행 가능 항목 (§A-3 와 충돌하지 않음):
- §0-1 잔여: `Dockerfile` / `docker-compose.test.yml` — §G-3 CI 와 같은 PR로 묶어도 무방.
- §0-3 잔여: alembic 호환성 통합 테스트 1건.
- §C-1 (Lunch Crawler) + §C-2 (Restaurants Crawler) 진행 중 — §A-3 완료 이후 즉시 착수. §C-3 즉시 발송 worker 는 §C-1·C-2 완료 후 진행.
