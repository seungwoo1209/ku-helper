# Security rules

## Discord OAuth 흐름 (사용자 설치, `integration_type=1`)

1. `/auth/discord/login`: 서명된 `state`(5분 만료) JWT를 발급한 뒤, Discord 인가 URL로 `307` 리다이렉트한다. 인가 URL 쿼리에 `integration_type=1`을 포함한다.
2. `/auth/discord/callback`: `code`와 `state`를 검증한다. `state` 불일치는 즉시 401.
3. Discord `/oauth2/token`으로 `code` 교환 → access token.
4. Discord `/users/@me`로 사용자 정보 조회.
5. `discord_id`로 사용자를 upsert한다 (없으면 생성, 있으면 갱신).
6. 우리 서버의 자체 JWT를 발급해 응답한다.

OAuth scope는 최소화한다. 현재는 `identify`만 요청. `email`·`guilds.join`·`applications.commands` 등은 실제 필요한 기능이 생긴 시점에 추가한다.

Discord OAuth 클라이언트 라이브러리: `httpx-oauth`의 `DiscordOAuth2`. 의존성 생성은 `app/domains/auth/dependencies.py`에서 수행한다.

## 자체 JWT

- 알고리즘: `HS256`. 키 교체가 잦으면 `RS256`로 재검토.
- 페이로드: `sub`(우리 user id), `discord_id`, `exp`, `iat`, `jti`. 그 외 필드 금지.
- 만료: access 30분, refresh 30일. 두 토큰은 별도로 발급/검증한다.
- 검증은 `app/core/security.py`의 `get_current_user` 의존성을 통해서만 수행한다. 라우터·Service에서 `jwt.decode` 직접 호출 금지.

## 비밀 관리

- 모든 비밀(`JWT_SECRET`, `DISCORD_CLIENT_SECRET` 등)은 `Settings`에서 `SecretStr`로 받는다.
- `SecretStr.get_secret_value()`는 검증 직전에만 호출한다.
- 로그, 응답, 예외 메시지에 비밀이 포함되지 않는지 확인한다.
- `.env`는 `.gitignore`에 포함되어 있어야 한다. PR에서 `.env`가 추가되면 즉시 거절.

## 권한

- 권한 검사는 라우터의 `Depends`로 합성한다: `user: Annotated[User, Depends(require_role("admin"))]`.
- Service에서 `if user.role == ...` 분기를 두지 않는다. 권한은 라우터 진입 시점에 끝낸다.

## CORS

- 허용 origin은 `Settings.cors_origins: list[str]`로 명시한다. `*` 금지.
- `allow_credentials=True`와 `*` origin은 함께 사용할 수 없다 (브라우저가 거부).

## Discord 봇 토큰

현재 환영 DM 발송에 봇 토큰을 사용한다. 향후 추가 봇 API(슬래시 커맨드 등) 호출도 같은 규칙을 따른다.

- 봇 토큰은 절대 클라이언트에 노출되지 않는다. 봇 API 호출은 서버에서만 수행한다.
- 봇 토큰을 사용하는 함수는 `app/core/discord.py`에 격리한다 (`DiscordBotClient`).
- DM 발송 흐름: `POST /users/@me/channels`(채널 생성) → `POST /channels/{channel_id}/messages`(메시지 전송). 두 호출 모두 봇 토큰을 `Authorization: Bot <token>` 헤더로 보낸다.
- Discord API `429` 응답은 외부 클라이언트 래퍼에서 처리한다 (`Retry-After` 헤더 준수, 최대 3회 재시도). Service는 rate limit을 모른다. 재시도 정책은 클라이언트 계층의 책임.
- DM 발송 실패는 베스트 에포트로 처리(로그인 흐름을 막지 않음). 라우터의 `BackgroundTasks`로 응답 종료 후 비동기 실행.

## 입력 검증

- 모든 요청 본문은 Pydantic 스키마로 받는다. `request.json()`을 직접 호출하지 않는다.
- 외부에서 받은 ID(특히 Discord ID)는 그대로 SQL 조건에 넣어도 안전하다 (ORM이 파라미터화). 단, 로그에 출력할 때는 화이트리스트 검증.