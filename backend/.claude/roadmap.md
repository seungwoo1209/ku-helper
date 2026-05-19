# Backend Roadmap

다음 세션이 백엔드에 다시 들어올 때 참고할 잔여 작업·정책 미결 사항·잠재 부채 목록.
현재 봇 컨테이너 작업이 우선이라 잠시 보류 중이지만, 백엔드 PR을 다시 시작할 때
**여기서부터 읽어서 컨텍스트를 복구**할 것.

마지막 갱신: 2026-05-20 (D-4 부채 폐기 — `backend/routes/lunch.py` 경로·`bot/scrapers/` 일괄 삭제. 프론트 LunchScreen 라이브 패널은 의도적으로 보존하지 않고 그대로 두어 `/api/lunch/today` 가 404 가 되는 회귀를 수용).

## 진행 상황 스냅샷

완료된 마일스톤
1. Auth 도메인: Discord OAuth(user-install, `integration_type=1`) 로그인·콜백
2. Users 도메인: `GET/DELETE /users/me` + 소프트 삭제 + role/status 컬럼
3. Notifications 도메인: 교통/점심/도서관 CRUD (`/me/notifications/*`) + JSONB config + history 테이블 (라우터 X)
4. 테스트 인프라 + 회귀 가드(`session.refresh`, `soft_delete UPDATE`, history cascade)

알려진 잠재 부채는 §C·§D 참고.

## A. 작은 보강 작업

### A-1. `PATCH /users/me` 스텁 채우기  (우선순위: 낮음)
- **현재**: `app/domains/users/router.py` PATCH 핸들러가 `NotImplementedError`, `UserUpdate` 스키마는 빈 `pass`.
- **선결**: 무엇을 수정 가능하게 할지 정책 결정 — 클라이언트가 `discord_username` 캐시를 동기화할지, 표시 이름을 별도로 둘지. 봇 컨테이너에서 사용자명을 어떻게 다룰지와 묶어서 결정해야 한다.
- **scope**: 한 PR.

### A-2. `Settings.jwt_secret` 길이 검증  (우선순위: 보통)
- **현재**: 16바이트로 짧음. 테스트에서 `InsecureKeyLengthWarning` 다발.
- **변경**: `app/core/config.py`에 pydantic `field_validator`로 `len(get_secret_value()) >= 32` 강제.
- **운영 적용**: 시크릿 회전 절차와 함께. `.env` 갱신 가이드를 PR description에 명시.

## B. 중기 — F-18 · 관리자

### B-1. `require_role` 가드 + 관리자 라우터 (F-23)  (우선순위: 높음)
- **현재**: `User.role` 컬럼은 0003에서 추가되어 존재하나 가드/라우터 없음.
- **추가**:
  - `app/core/security.py`에 `def require_role(role: UserRole) -> Callable[..., Awaitable[User]]` 헬퍼.
    내부에서 `Depends(get_current_user)` + `UserRole` 비교 → 도메인 예외 `NotAuthorizedForRole`(403).
  - `app/domains/admin/` 도메인 신설 (CLAUDE.md의 6-파일 규칙). 라우터 prefix `/admin`.
  - 첫 엔드포인트: `GET /admin/health`(권한 가드만 검증) → 이후 알림 발송 통계 등 확장.
- **테스트**: happy(ADMIN) + forbidden(USER) 두 케이스.

### B-2. F-18 활성 시간대  (우선순위: 보통, 봇 합의 후)
- **요구사항**: 평일/주말 별 알림 수신 시작·종료 시각.
- **저장 위치 결정 필요**:
  - User 레벨: `users`에 `quiet_hours_weekday`, `quiet_hours_weekend` 컬럼 또는 `user_preferences` 테이블 분리
  - 알림 항목별 `config` JSONB 안에 포함 (항목마다 다른 시간대 가능)
- **봇 컨테이너 결정과 묶임**: 폴링 쿼리에서 시간대 필터를 어디서 평가할지 봇 측과 합의.

## C. 인프라 / 보안 결정

### C-1. Redis 도입  (우선순위: 높음, C-2 풀리려면 선행 필요)
- **architecture.md 명시**: state 토큰·캐시·쿨다운·관리자 알림 dedupe.
- **현재 격차**: state 토큰은 JWT(stateless)로 구현 중. 캐시는 없음.
- **단계**:
  1. `Settings.redis_url` 추가 + `docker-compose-dev.yml`에 redis 서비스.
  2. lifespan에서 `redis.asyncio.from_url` 클라이언트 생성·종료.
  3. OAuth state 토큰을 Redis로 이전 (TTL 5분). 단, JWT 방식 그대로 두고 캐시·블랙리스트만 Redis로 갈 수도 있음 — 비용/장애 면 검토.

### C-2. F-02 로그아웃 / F-05 토큰 갱신  (C-1 이후)
- `POST /api/v1/auth/refresh`: refresh 토큰 검증 → 새 access 발급.
- `POST /api/v1/auth/logout`: refresh `jti`를 Redis 블랙리스트에 등록 (TTL = 남은 만료).
- `decode_token`에서 블랙리스트 확인 단계 추가.
- 테스트: respx 무관 (외부 호출 없음), 단위·통합 둘 다 가능.

## D. 알려진 부채·잠재 회귀

### D-1. `get_current_user`의 별도 세션 사용
- **위치**: `app/core/security.py:get_current_user`가 `async_session_maker`로 직접 short-lived 세션을 연다.
- **결과**:
  - 라우터의 request-scoped 세션과 분리 → 반환된 `User`가 detached.
  - service에서 ORM 속성 대입이 무효화되는 회귀 패턴 발생 (한 번 잡힌 `soft_delete` 회귀의 근본 원인).
  - 통합 테스트가 `dependency_overrides[get_current_user]`로 우회하므로 "USER_DELETED 차단" 시나리오를 정확히 재현 못함.
- **해결 후보**:
  - `app/domains/users/dependencies.py`로 `get_current_user`를 옮기고 `Depends(get_session)`을 받음. `app/core/security.py`는 토큰 인코딩/디코딩만 남김. 도메인 import 순환은 자연스럽게 풀린다.
- **시점**: C-1(Redis 블랙리스트)을 도입하면서 `get_current_user`를 어차피 손대게 되므로 같이.

### D-2. alembic 자체 회귀를 테스트가 못 잡음
- **현재**: `tests/conftest.py:test_engine`이 `Base.metadata.create_all`로 스키마 셋업. alembic upgrade 경로는 안 돌아감.
- **결과**: 0004에서 발생했던 "asyncpg + create_type=False 무시" 같은 마이그레이션 자체의 버그를 통합 테스트가 못 잡음. 수동 dev 실행에서만 발견.
- **해결안**: 별 fixture `test_engine_via_alembic`을 만들고 핵심 마이그레이션 왕복 테스트 1개(upgrade head → downgrade base → upgrade head)만 추가. 일반 테스트 fixture는 그대로 create_all 유지(빠름).

### D-3. CI 워크플로 부재
- GitHub Actions 미구성. 매 PR 수동 검증 중.
- 워크플로: docker-compose.test.yml 기동 + `uv sync` + `uv run ruff check` + `uv run mypy app tests` + `uv run pytest --cov`.
- 별 PR로 가벼움. 위 어느 작업에든 합쳐도 무방.

### D-5. 폐기 예정 — `immediate_send_requests` 임시 구조
- **위치**: `app/domains/immediate_send/` 도메인, `immediate_send_requests` 테이블, `notification_history.immediate_send_request_id` 컬럼, 알embic 0005.
- **존재 사유**: "즉시 lunch DM" 종단 검증용. 프론트 버튼 → 백엔드 INSERT → 봇 폴링 → DM. 컨테이너 경계(PG 매개) 를 준수하면서 즉시성 확보.
- **잠재 확장**: 도메인 `type` enum 이 TRANSIT/LUNCH/LIBRARY 모두 받게 설계됨. 현재 LUNCH 만 사용. 후속에 transit/library 도 같은 경로로 확장 가능.
- **폐기 조건**: 정식 알림 시스템(스케줄 + on-demand 통합) 도입 시 도메인·테이블·컬럼·라우터 일괄 제거. 그때까지 추가 기능은 이 도메인에 넣지 말고 정식 알림 시스템으로 가는 게 원칙.
- **연결 부채**: 봇 측 `bot/app/notifications/lunch/` 워커도 같은 라이프사이클. 함께 폐기.

## E. 봇 컨테이너 흐름과 맞물리는 영역 (백엔드 측 책임 한정)

### E-1. 봇 인터페이스 합의
- 봇이 폴링할 쿼리 형태는 이미 인덱스 준비됨 (`ix_notifications_user_id_enabled`).
- 결정 필요:
  - `notification_history.payload` JSONB 스키마 (임베드 스냅샷 포맷).
  - 환영 DM 발송 책임: 현재 `app/domains/auth/service.py:maybe_send_welcome_dm` → `app/core/discord.py:DiscordBotClient`. 봇 컨테이너 분리 시 어디서 발송할지.
  - 봇 → 백엔드 통신 채널: PostgreSQL 매개(architecture.md 기본) vs HTTP 콜백.

### E-2. F-22 크롤러 실패 — 백엔드 책임 부분
- 봇이 실패 이력을 PostgreSQL에 적재하는 모델을 채택하면 `crawler_failures` 테이블만 백엔드에서 정의·마이그레이션.
- 관리자 조회는 B-1의 admin 라우터에 합류.

## 권장 순서

**B-1 (require_role) → A-2 (jwt 길이) → D-1 (get_current_user 리팩터) → C-1 (Redis) → C-2 (로그아웃/refresh) → B-2 (활성 시간대, 봇 합의 후) → D-2 (alembic 왕복) → D-3 (CI) → A-1 (PATCH /me) → E-* (봇 합의 후)**

봇 컨테이너 작업과 병행할 때 가장 충돌이 적은 영역은 **B-1 / A-2 / D-1 / D-3**.
