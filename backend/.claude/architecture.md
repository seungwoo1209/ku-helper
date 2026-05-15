# Architecture rules

CLAUDE.md의 7개 절대 규칙을 보강한다. 충돌 시 CLAUDE.md가 우선.

## Router

- `APIRouter`만 정의하고 `prefix`, `tags`를 명시한다.
- 함수 본문은 (1) 요청 스키마 수신, (2) 의존성 주입, (3) Service 호출, (4) 응답 스키마 반환의 4단계로 제한한다.
- `if`, `for`, `try`가 라우터 안에 들어가면 거의 항상 Service로 옮긴다.
- `response_model`과 `status_code`를 항상 명시한다.

## Service

- `__init__`에서 모든 의존성을 받는다. Service 내부에서 다른 Service나 Repository를 직접 import해 인스턴스화하지 않는다.
- 도메인 예외(`UserNotFound`, `InvalidNotificationConfig`, `DiscordGuildJoinFailed` 등)만 발생시킨다.
- 트랜잭션 커밋은 `get_session` 의존성이 담당한다. Service는 명시적으로 `commit()`을 호출하지 않는다.
- 외부 API 호출은 라이프스팬에서 만든 공유 클라이언트를 의존성으로 받는다.

## Repository

- 반환 타입은 ORM 모델 또는 도메인 객체. `Row`, `dict`, `tuple`을 그대로 반환하지 않는다.
- 메서드 이름은 의도를 드러낸다: `get_by_discord_id`, `list_active_subscriptions`, `exists_by_email`. `select_*`, `query_*` 금지.
- N+1 회피용 로딩 전략(`selectinload`, `joinedload`)은 Repository에서 처리한다. Service는 모른다.

## Schema

- 응답 스키마는 `model_config = ConfigDict(from_attributes=True)`로 설정한다.
- ORM 모델을 라우터에서 그대로 반환하지 않는다. 항상 `ResponseSchema.model_validate(orm_obj)`로 변환한다.
- 입력 스키마에서 비밀 값은 `SecretStr`을 사용한다.
- 같은 도메인의 `Create`/`Update`/`Read`는 공통 기반 클래스로 묶지 않는다. 각자 독립적으로 두는 게 변경 비용이 낮다.

## Dependencies

- 도메인별 `dependencies.py`에 의존성 함수를 모은다.
- 모든 외부 의존(DB 세션, HTTP 클라이언트, Service 인스턴스)은 `Depends`로 주입한다.
- 의존성 함수의 반환 타입은 명시한다.

## Lifespan

- 공유 리소스는 `app.main`의 `lifespan`에서 한 번만 생성한다.
  - `httpx.AsyncClient` (Discord API 호출용, timeout 명시)
  - 필요 시 Redis, 캐시 클라이언트
- 종료 시 전부 `close` 또는 `aclose`를 호출한다.
- 요청마다 새 `AsyncClient()`를 만드는 코드는 PR 거절 사유.

## 예외 핸들러

- `app.main`에서 도메인 예외를 등록한다.
- 응답 포맷: `{"code": "USER_NOT_FOUND", "detail": "사람이 읽는 메시지"}`. 클라이언트는 `code`로 분기한다.
- `code`는 `SCREAMING_SNAKE_CASE`. 도메인 예외 클래스마다 1:1로 매핑한다.

## 트랜잭션 경계

- 한 요청 = 한 트랜잭션이 기본.
- 여러 도메인을 가로지르는 작업은 라우터 또는 상위 Service가 트랜잭션 경계를 결정한다. 하위 Service는 자기 트랜잭션을 열지 않는다.