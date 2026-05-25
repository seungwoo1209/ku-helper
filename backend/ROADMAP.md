# Backend Roadmap

다음 세션이 백엔드에 다시 들어올 때 참고할 잔여 작업·정책 미결 사항·잠재 부채 목록.
현재 봇 컨테이너 작업이 우선이라 잠시 보류 중이지만, 백엔드 PR을 다시 시작할 때
**여기서부터 읽어서 컨텍스트를 복구**할 것.

마지막 갱신: 2026-05-25 — C-3 RDS·ElastiCache IAM DB 인증 적용(issue #34, 브랜치 `infra/aws-rebuild`). `Settings` 에 `use_iam_auth: bool`(기본 False) + `aws_region` + `db_host/port/name/iam_user` + `redis_host/port/iam_user/cache_name` 추가. `database_url`/`redis_url` 은 default `""` 로 완화 + `model_validator` 로 분기별 필수 검증. 신규 `app/core/aws_auth.py` (boto3 `generate_db_auth_token` + `SigV4QueryAuth` 기반 ElastiCache token, 15분 만료). `database.py` 가 `do_connect` 이벤트로 매 connect 시 RDS IAM 토큰 재발급(`ssl=require`). `redis.py` 가 redis-py 5.0+ `CredentialProvider` 추상으로 매 connect 시 SigV4 토큰 재발급. `create_redis_client` 시그니처 `(url)` → `(settings)`. `alembic/env.py` 는 `ALEMBIC_DATABASE_URL` / `DATABASE_URL` 환경변수 우선(운영 마이그레이션은 워크플로가 master 패스워드로 조립). `backend/Dockerfile` 신규(multi-stage uv + non-root). `pyproject.toml` boto3>=1.34. 회귀 가드 0건(후속 §C-3 메모). 이전: D-1 `get_current_user` 리팩터 완료(issue #20, 브랜치 `refactor/d1-get-current-user-deps`). `get_current_user`/`require_role`/`_bearer_scheme` 을 `domains/users/dependencies.py` 로 이전하고 `Depends(get_user_repository)` 시그니처로 라우터 세션 공유 — production 의 detached User 경로 제거. `core/security.py` 함수 내부 동적 import 사라져 `core → domains` 역방향 의존 해소. `repository.py:soft_delete` 의 명시 UPDATE 워크어라운드 제거 → ORM 속성 대입+flush. 테스트 픽스처 `db_session.expunge(...)` 잔재 4 곳 정리. 신규 가드 `tests/domains/users/test_auth_guard.py` 2건(실 JWT + 실 DB DELETED/ACTIVE). 테스트 62 → 67(+5). 이전: B-1 `require_role` + admin 라우터 완료 확인. 이전: C-1 Redis 인프라 + C-2 refresh/logout(whitelist) + OAuth state 1회용화 완료. `Settings.redis_url`(required) + `app/core/redis.py`(`create_redis_client`) + lifespan 에 `app.state.redis` 도입. `security.py` 에 `register_refresh_jti` / `revoke_refresh_jti` / `assert_refresh_jti_active` 3개 헬퍼 + `create_refresh_token` 시그니처 변경(`tuple[str, str]` 반환). `AuthService.__init__` 에 redis 주입, `handle_callback` 이 발급 직후 jti SETEX(TTL = `jwt_refresh_expiry_days * 86400`). 신규 `POST /api/v1/auth/refresh`(rotation: old jti DEL → new jti SET) + `POST /api/v1/auth/logout`(jti DEL, idempotent 204). 라우터 prefix `/auth/discord` → `/auth` 변경(엔드포인트 URL 유지: `/auth/discord/login`, `/auth/discord/callback`, 신규 `/auth/refresh`, `/auth/logout`). OAuth state 1회용화: `verify_state_token` 시그니처 `-> dict[str, Any]` 로 확장, 신규 `consume_state_jti(redis, jti)` 가 `state_used:{jti}` SET NX EX `jwt_state_expiry_minutes*60` — `handle_callback` 이 state 검증 직후 호출해 같은 state 두 번째 콜백을 401 로 차단(replay 가 Discord 외부 호출까지 새지 않는 회귀 가드 포함). 테스트 56 → 62(+6: refresh 5건 + state replay 1건). conftest 에 fakeredis `redis_client` 픽스처 + `app.state.redis` 오버라이드. 이전: F-06 TRANSIT 단발 알림 스키마 확장(커밋 `dcb5ab2`).

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

### B-1. `require_role` 가드 + 관리자 라우터 (F-23) — 완료
- `app/core/security.py:208` `require_role(role: UserRole) -> Callable[..., Awaitable[User]]` 헬퍼 — `Depends(get_current_user)` 합성 후 `current_user.role != role` 비교 → `NotAuthorizedForRole`(403).
- `app/domains/admin/` 6 파일 모두 작성. 라우터 prefix `/admin`, 첫 엔드포인트 `GET /admin/health` → `AdminHealthRead({"status": "ok"})` 반환. 401/403 responses OpenAPI 문서화 완료.
- F-23 관리자 대시보드 신규 엔드포인트는 같은 `Depends(require_role(UserRole.ADMIN))` 패턴 재사용.

### B-2. F-18 활성 시간대  (우선순위: 보통, 봇 합의 후)
- **요구사항**: 평일/주말 별 알림 수신 시작·종료 시각.
- **저장 위치 결정 필요**:
  - User 레벨: `users`에 `quiet_hours_weekday`, `quiet_hours_weekend` 컬럼 또는 `user_preferences` 테이블 분리
  - 알림 항목별 `config` JSONB 안에 포함 (항목마다 다른 시간대 가능)
- **봇 컨테이너 결정과 묶임**: 폴링 쿼리에서 시간대 필터를 어디서 평가할지 봇 측과 합의.

## C. 인프라 / 보안 결정

### C-1. Redis 도입  — 완료 (refresh whitelist + state 1회용화 + 봇 크롤러 캐시 4종)
- 완료: `Settings.redis_url`(required) + `app/core/redis.py` + lifespan(`app.state.redis`) + `redis>=5.0` / dev `fakeredis>=2.20`.
- 사용처:
  - `refresh_jti:{jti}` TTL 30d — refresh token whitelist (C-2).
  - `state_used:{jti}` TTL `jwt_state_expiry_minutes*60` — OAuth state 1회용 잠금. `consume_state_jti` 가 SET NX 으로 잠그며 두 번째 콜백은 NX 실패로 401.
  - 봇 측 크롤러 4종 + F-14 도서관 상태머신 + F-06 단발 도착 dedup 은 bot roadmap §C-1 참고.
- **후속 작업**:
  - `infra/docker-compose-*.yml` 류에 redis 서비스 정식 추가 (현재 dev/test compose 는 backend/ 하위에 있고 redis 서비스 부재 — 호스트 redis 가정).

### C-3. RDS·ElastiCache IAM DB 인증 — 부분 완료 (issue #34)
- **완료**: `Settings.use_iam_auth` 분기 + `app/core/aws_auth.py` (`generate_rds_iam_token` / `generate_elasticache_iam_token`) + `database.py` 의 `do_connect` 이벤트 + `redis.py` 의 `CredentialProvider`. 로컬 dev/test 는 `USE_IAM_AUTH=false` 기본으로 회귀 없음. `backend/Dockerfile` 신규.
- **운영 진입 조건**: `infra/ephemeral` 가 SSM Parameter (`/ku-helper/app/USE_IAM_AUTH=true` 외 호스트 변수들) 와 RDS 안 `rds_iam` grant 를 사전 수행해야 함. spin-up.yml 워크플로 첫 실행 시 bastion 경유 master 패스워드 SQL 1회 실행 — `infra/ephemeral/README.md` 참고.
- **alembic**: `ALEMBIC_DATABASE_URL` 환경변수 우선 사용. workflow 가 RDS master 패스워드를 Secrets Manager 에서 fetch 해 조립한 URL 로 마이그레이션 실행.
- **잔여**:
  - 단위 테스트 미작성. 후보: (1) `Settings` validator 분기 2건 (USE_IAM_AUTH true/false 누락 필드), (2) `aws_auth.generate_rds_iam_token` 의 boto3 호출 인자 검증(mock), (3) `redis._ElastiCacheIamCredentialProvider.get_credentials` 가 매 호출마다 새 토큰 발급하는지(mocked SigV4QueryAuth).
  - ElastiCache SigV4 토큰 형식이 AWS 환경별로 미세하게 다를 수 있어 실 운영 첫 spin-up 후 검증 필요(`removeprefix("http://")` 분리 자체는 공식 패턴).
  - bot 컨테이너에도 동일 패턴 적용 — bot roadmap §0-4 참고.

### C-2. F-02 로그아웃 / F-05 토큰 갱신  — 완료
- `POST /api/v1/auth/refresh`: refresh JWT 검증 → jti whitelist 확인 → rotation(old DEL + new SET) → 새 access/refresh 발급.
- `POST /api/v1/auth/logout`: refresh jti 를 Redis whitelist 에서 DEL (idempotent 204).
- Access 토큰은 stateless 유지 — 별도 블랙리스트 미도입(만료 30분으로 짧음). 즉시 차단이 필요해지면 별 PR.
- 회귀 가드 5건: rotation·재사용 차단·만료 거절·logout 후 refresh 401·logout idempotent.

## D. 알려진 부채·잠재 회귀

### D-1. `get_current_user`의 별도 세션 사용 — 완료 (issue #20, 브랜치 `refactor/d1-get-current-user-deps`)
- `get_current_user` + `require_role` 을 `app/domains/users/dependencies.py` 로 이전 + `Depends(get_user_repository)` 시그니처 — 라우터 세션 공유. `_bearer_scheme` 도 같은 모듈로.
- `app/core/security.py` 함수 내부 동적 import 제거 → `core → domains` 역방향 의존 사라짐. 토큰 인코딩/디코딩·OAuth state·refresh whitelist 헬퍼만 남음 (예외 4종 잔존).
- `repository.py:soft_delete` 명시 UPDATE 워크어라운드 제거 → `user.status = DELETED; await flush()` 단순 ORM 패턴 복원.
- 테스트 픽스처(`authed_client`, `admin_authed_client`) 의 `db_session.expunge(user)` 시뮬레이션 제거 — production 의 detached 경로가 더 이상 존재하지 않으므로 시뮬레이션 자체가 잘못된 가드였음.
- 신규 회귀 가드 `tests/domains/users/test_auth_guard.py` 2건: `dependency_overrides` 우회 없이 실 JWT + 실 DB 로 ACTIVE → 200, DELETED → 401 `USER_DELETED` 검증.

### D-2. alembic 자체 회귀를 테스트가 못 잡음
- **현재**: `tests/conftest.py:test_engine`이 `Base.metadata.create_all`로 스키마 셋업. alembic upgrade 경로는 안 돌아감.
- **결과**: 0004에서 발생했던 "asyncpg + create_type=False 무시" 같은 마이그레이션 자체의 버그를 통합 테스트가 못 잡음. 수동 dev 실행에서만 발견.
- **해결안**: 별 fixture `test_engine_via_alembic`을 만들고 핵심 마이그레이션 왕복 테스트 1개(upgrade head → downgrade base → upgrade head)만 추가. 일반 테스트 fixture는 그대로 create_all 유지(빠름).

### D-3. CI 워크플로 부재
- GitHub Actions 미구성. 매 PR 수동 검증 중.
- 워크플로: docker-compose.test.yml 기동 + `uv sync` + `uv run ruff check` + `uv run mypy app tests` + `uv run pytest --cov`.
- 별 PR로 가벼움. 위 어느 작업에든 합쳐도 무방.

### D-4. Refresh JTI Redis TTL 드리프트 (우선순위: 낮음)
- **현재**: `security.py:register_refresh_jti` 가 TTL 을 `jwt_refresh_expiry_days * 86400` 고정 계산. rotation 시 새 Redis 키가 JWT `exp` 와 ms 단위로 어긋남.
- **영향**: `decode_token()` 이 JWT 만료를 먼저 검증해 Redis 도달 전에 차단 → 보안 무해, 메모리 미세 낭비뿐.
- **해결안**: `register_refresh_jti(redis, jti, user_id, exp)` 로 시그니처 변경, TTL = `int(exp) - int(now().timestamp())` 로 계산.
- **시점**: 메모리 사용 지표가 거슬릴 때. 그 전까지 보류. (PR #10 review)

### D-6. 만료된 refresh 토큰 logout 정책 (우선순위: 낮음)
- **현재**: `logout()` 이 `decode_token()` 호출 → 만료된 refresh 토큰으로 logout 시 401. 의미상 idempotent 와 어긋남.
- **영향**: Redis JTI 키는 자동 만료되므로 보안 영향 없음. 사용자 경험만 미세하게 어색.
- **해결안 후보**: (a) `decode_token` 에 `verify_exp=False` 옵션 추가하고 logout 만 그 옵션 사용, (b) 클라이언트가 토큰 만료 전 logout 하도록 가이드. (a) 는 검증 로직이 보안 경로에 직접 닿으므로 신중. 정책 결정이 먼저.
- **시점**: 클라이언트 사이드에서 만료 토큰 logout 시도 빈도 측정 후. (PR #10 review)

### D-5. 정식 on-demand 알림 채널 — `immediate_send_requests`
- **위치**: `app/domains/immediate_send/` 도메인, `immediate_send_requests` 테이블, `notification_history.immediate_send_request_id` 컬럼, alembic 0005.
- **역할**: "프론트 버튼 → 백엔드 INSERT → 봇 폴링 → DM" 경로로 알림 종류별 즉시 발송을 제공한다. 컨테이너 경계(PG 매개)를 준수하면서 즉시성을 확보하는 정식 채널이며, 정기 알림 시스템과 별개 경로로 공존한다.
- **현재 가동 종류**: LUNCH (`POST /api/v1/me/immediate-send/lunch`), TRANSIT (`.../transit`), LIBRARY (`.../library`) — 3종 모두 운영. LIBRARY body 는 `reading_room_id: Literal[0,1,2,3,5]`(0=전체 합산), payload `{"reading_room_id": N}`. 봇 워커 `run_immediate_send_library_job` 와 짝.
- **확장 패턴**: 도메인 `type` enum 은 TRANSIT/LUNCH/LIBRARY 모두 받는다. 새 종류 추가는 다음 4 단계.
  1. `schemas.py` 에 `<Type>DispatchRequest`/`<Type>DispatchResponse` 추가 + Field description/examples 동봉.
  2. `service.py` 에 `request_<type>_dispatch(user, body)` 메서드 — `payload` 는 봇 워커가 필요로 하는 키만 그대로 dict 화.
  3. `router.py` 에 `POST /<type>` 핸들러 추가 + `responses=` 401/422/429 문서화.
  4. 봇 측에 `app/notifications/<type>/repository.py` (LEFT JOIN 가드) + `run_immediate_send_<type>_job` worker + scheduler 잡 등록.
- **테이블/마이그레이션은 손대지 않는다** — 0005 가 이미 enum 3종 모두를 받게 만들어 둠. payload JSONB 는 알림 종류별 의미가 다른 자유 dict 라 새 컬럼을 늘리지 않는다.
- **`IMMEDIATE_SEND_RATE_LIMITED` 도메인 예외**: 정의돼 있으나 service 가 실제 rate-limit 검사를 수행하지 않는다 (별 PR). 정책 확정 후 service 진입 시점에 동일 user_id + pending 상태 검사 추가.
- **연결 채널**: 봇 측 `bot/app/notifications/<type>/` 워커가 짝을 이룬다. lunch/transit/library 즉시 발송 워커 3종 모두 가동(봇 roadmap §C-3, §D-4).

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

**~~C-1 (Redis)~~ → ~~C-2 (로그아웃/refresh)~~ → ~~OAuth state Redis 단발성 전환~~ → ~~B-1 (require_role)~~ → ~~D-1 (get_current_user 리팩터)~~ → A-2 (jwt 길이) → B-2 (활성 시간대, 봇 합의 후) → D-2 (alembic 왕복) → D-3 (CI) → A-1 (PATCH /me) → E-* (봇 합의 후)**

봇 컨테이너 작업과 병행할 때 가장 충돌이 적은 영역은 **A-2 / D-3**.
