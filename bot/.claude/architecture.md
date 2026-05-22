# Architecture rules

CLAUDE.md의 7개 절대 규칙을 보강한다. 충돌 시 CLAUDE.md가 우선.

봇 컨테이너는 4개 계층으로 구성된다: **Scheduler → Worker → (Crawler · Repository) → Sender**.
백엔드의 Router/Service/Repository와 매핑하면 Scheduler가 Router, Worker가 Service, Crawler/Repository가 Repository에 해당한다.

## Scheduler

- APScheduler `AsyncIOScheduler` 인스턴스 1개. 라이프스팬에서 생성·시작·종료.
- 잡 등록은 `app/scheduler/jobs.py`에 모아 lifespan에서 1회 수행한다. 런타임에 동적으로 추가하지 않는다.
- 잡 함수는 Worker를 호출만 한다. 분기·조건 평가·DB 조회를 잡 함수 안에 넣지 않는다.
- 잡 단위 실패는 `structlog`로 기록하고 다음 트리거를 막지 않는다 (`misfire_grace_time` 명시).

## Worker

- 위치: `app/notifications/<type>/worker.py`. 한 알림 종류 = 한 Worker.
- 책임: (1) `NotificationRepository`로 활성 구독 조회 → (2) Crawler 결과와 비교해 조건 평가 → (3) 임베드 빌드 → (4) Sender 큐 적재.
- Worker는 `discord.py` SDK 객체에 직접 의존하지 않는다 (Sender 책임).
- Worker는 `notification_history`에 직접 INSERT하지 않는다 (Sender 책임).

## Crawler

- 위치: `app/crawlers/<source>/client.py`. 외부 데이터 소스 1개 = 모듈 1개. 소스별 독립 갱신을 위해 통합하지 않는다.
- 응답은 정규화된 도메인 객체(dataclass 또는 Pydantic)로 반환. raw dict 노출 금지.
- Redis TTL 캐시, HTTP 재시도, 외부 사이트 크롤링 정책(최소 1초 간격 등)은 클라이언트 내부에서 처리한다. Worker는 캐시 존재 여부를 모른다.
- 크롤러 실패는 도메인 예외(`SubwayApiUnavailable`, `LibraryCrawlerFailed` 등)로 변환해 던진다. raw `httpx.HTTPStatusError`를 위로 흘리지 않는다.

## Repository

- SQLAlchemy `AsyncSession`. 종류는 2개:
  - `NotificationRepository`: `notifications` SELECT 전용(read-only).
  - `NotificationHistoryRepository`: `notification_history` INSERT 전용.
- UPDATE/DELETE 메서드는 정의하지 않는다. 백엔드가 cascade 책임을 진다.
- N+1 회피용 로딩 전략(`selectinload`, `joinedload`)은 Repository에서 처리한다. Worker는 모른다.

## Sender

- 위치: `app/notifications/sender.py`. 단일 `asyncio.Queue` + 단일 워커 태스크.
- 큐에서 발송 작업(`SendDmTask`)을 꺼내 `DiscordBotClient.send_embed`로 DM을 보내고, 결과를 `NotificationHistoryRepository.insert_result`로 기록한다.
- Discord API rate limit(초당 1건)을 준수하기 위해 큐 워커는 1개만 유지한다. 병렬 확장 금지.
- 발송 실패 시 지수 백오프(1·2·4초, 최대 3회) 재시도(F-21). 재시도 후에도 실패하면 history에 `FAILED`로 INSERT.

## Admin (F-22)

- 위치: `app/admin/alerts.py`.
- 공개 함수: `enqueue_admin_alerts(queue, settings, source, exc)` — 호출 즉시 `settings.admin_discord_ids` 전원에게 `SendDmTask` 1건씩 큐 적재.
- Single-trigger 정책: 크롤러 예외 1회 = admin DM 1회. 임계값·카운터·쿨다운 없음. 원본 요구사항(`docs/requirements/features.md` F-22: "실패 시 1분 이내 DM") 직역.
- admin DM 도 일반 사용자 알림과 동일 Sender 큐를 통과한다. 별 발송 경로 없음.
- 실 운영에서 노이즈 폭주가 관찰되면 가드(임계값·5분 윈도우 카운터·30분 쿨다운) 재도입 — `bot/.claude/roadmap.md` §E 신규 후속 항목 참고.

## 상태 기반 중복 방지 (F-14, 도서관)

- Redis 키 `library_alert:{user_id}:{room_id}` = `"above"` 또는 `"below"`.
- 잔여석이 임계값 위로 회복되면 `above`, 임계값 아래로 떨어지면 `below`로 전환.
- 발송 조건: 직전 상태가 `above`이고 현재 임계값 이하 → 발송 후 `below`로 갱신.
- 시간 기반 쿨다운이 아니다 (회복 없이 계속 임계값 이하면 재발송하지 않는다).

## 트랜잭션 경계

- 한 잡 실행 = 한 트랜잭션. Worker가 사용한 세션은 잡 종료 시 커밋.
- Sender는 발송 결과 INSERT를 자기 트랜잭션으로 별도 커밋한다 (잡 트랜잭션과 분리).
- "발송 성공 + history INSERT 실패" 시나리오는 명시적으로 인지: 보정하지 않는다. 중복 발송 방지(F-14)가 정확성보다 우선이라 history 누락이 발생해도 같은 알림을 재발송하지 않는다.

## 백엔드와의 경계

- `users.status == DELETED` 사용자에게는 발송하지 않는다. `NotificationRepository`가 JOIN 필터로 1차 차단, Sender가 발송 직전 한 번 더 검증(이중 가드).
- 봇은 `users` 테이블·`notifications` 테이블·`User.status`를 변경하지 않는다.
- 환영 DM, 관리자 알림 외 임의의 DM 발송 진입점을 두지 않는다. 모든 발송은 Sender 큐를 통과한다.

## Lifespan (`app/main.py`)

공유 리소스는 lifespan에서 1회 생성한다:
- `discord.Client` (intents 최소화)
- `AsyncIOScheduler`
- `redis.asyncio.Redis`
- SQLAlchemy `async_sessionmaker`
- `httpx.AsyncClient` (공공 API용, timeout 명시)
- Sender 큐 워커 태스크

종료 시 전부 `close`/`aclose` 호출. 잡 함수마다 새 `AsyncClient()`나 새 Redis 풀을 만드는 코드는 PR 거절 사유.

## 예외 처리

- 도메인 예외 클래스는 `app/<layer>/exceptions.py`에 정의. (`SubwayApiUnavailable`, `LibraryCrawlerFailed`, `DiscordDmDeliveryFailed` 등)
- 잡 함수의 최상단에서 잡힌 도메인 예외는 (1) `structlog`로 키-값 로깅, (2) Admin 카운터 INCR, (3) 다음 트리거를 막지 않도록 swallow.
