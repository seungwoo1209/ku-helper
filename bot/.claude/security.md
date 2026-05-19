# Security rules

## Discord 봇 토큰 격리

- `Settings.discord_bot_token: SecretStr`. 다른 형으로 받지 않는다.
- `SecretStr.get_secret_value()` 호출은 `app/core/discord.py`의 `DiscordBotClient` 내부에서만 허용. 다른 모듈에서 호출하면 PR 거절.
- discord.py `Client.start(token)` 호출도 lifespan(`app/main.py`)이 직접 토큰을 꺼내는 게 아니라 `DiscordBotClient.start()` 같은 래퍼 메서드에 위임한다.
- 로그·예외 메시지·임베드에 토큰이 절대 포함되지 않는다 (`SecretStr`가 1차 방어).
- `.env`는 `.gitignore`에 포함. PR에서 `.env`가 추가되면 즉시 거절.

## DB 접근 권한 최소화

- 봇 컨테이너용 DB 사용자는 백엔드와 별도(`bot_runner`). 인프라 레벨에서 다음 권한만 grant:
  - `SELECT ON users, notifications, notification_history`
  - `INSERT ON notification_history`
  - 시퀀스 `USAGE`(history PK 발급용)
- UPDATE/DELETE 권한 자체가 없다. 코드에서도 호출 메서드를 정의하지 않는다.
- `app/db/models.py`는 백엔드 스키마와 형상만 일치하면 되고, 마이그레이션 생성·실행 권한은 없다. `alembic` 의존성 자체를 `pyproject.toml`에 넣지 않는다.

## 사용자 상태 가드

- 발송 직전 `user.status == ACTIVE`인지 검증한다 (이중 가드):
  1. `NotificationRepository.list_active_subscriptions`가 JOIN으로 `users.status = 'ACTIVE'`를 필터.
  2. Sender 워커가 큐에서 꺼낸 시점에 다시 한 번 확인.
- `DELETED` 사용자에게 DM이 발송되는 회귀는 개인정보 보호 위반 + 백엔드 cascade 일관성 파괴이므로 통합 테스트로 가드한다.

## PII 로깅

- 로깅 가능: `user_id`(우리 PK), `discord_id`, `notification_id`, `notification_type`, `delivery_status`.
- 로깅 금지: 임베드 본문, DM 메시지 내용, 사용자가 입력한 자유 텍스트.
- 필요 시 길이만 로그(`embed_length=512`).

## Rate limit 우회 금지

- `discord.HTTPException` 429를 무시하고 즉시 재시도하는 코드는 PR 거절.
- `app/core/discord.py`의 래퍼가 `Retry-After` 헤더를 준수해 백오프한다.
- 발송 큐 워커를 2개 이상으로 늘려 throughput을 올리려는 시도 금지 (Discord rate limit 초과 위험).

## 공공 API 키

- 서울 공공 API 키·학교 사이트 인증 정보는 `SecretStr`.
- 키가 URL query string에 포함되는 형태의 API라면 로그에서 마스킹(`url_template` 변수에 자리표시자만 둔다).
- 외부 호출 timeout 명시. `httpx.AsyncClient(timeout=10.0)` 같이.
- Subway API 키는 URL path 의 일부로 들어가므로 로그 출력 시 key 자리를 자리표시자로 마스킹한다.

## F-22 관리자 식별

- 관리자 Discord ID는 `Settings.admin_discord_ids: list[int]` 화이트리스트로 정적 관리.
- 런타임에 DB·외부 시스템에서 관리자 목록을 끌어오지 않는다 (권한 escalation 경로 차단).
- 관리자 DM 발송도 일반 알림과 동일한 Sender 큐를 거친다 (별도 경로 없음).

## 입력 검증 (외부 데이터)

- 외부 API·크롤링 결과를 Pydantic 모델로 받아 검증한 뒤에만 도메인 객체로 변환한다.
- 외부 응답을 그대로 임베드에 끼워 넣지 않는다 (Discord embed 길이 제한, HTML injection 방지).
- discord.py가 embed 길이를 초과하면 예외를 던지므로, 빌더에서 미리 절단하고 절단 사실을 로그에 남긴다.
