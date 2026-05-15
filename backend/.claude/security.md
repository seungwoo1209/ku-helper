# Security rules

## Discord OAuth 흐름

1. `/auth/discord/login`: Discord 인증 URL을 생성한다. `state`는 짧은 만료(5분)의 서명된 값으로 발급한다.
2. `/auth/discord/callback`: `code`와 `state`를 검증한다. `state` 불일치는 즉시 401.
3. Discord `/oauth2/token`으로 `code` 교환 → access token.
4. Discord `/users/@me`로 사용자 정보 조회.
5. `discord_id`로 사용자를 upsert한다 (없으면 생성, 있으면 갱신).
6. 우리 서버의 자체 JWT를 발급해 응답한다.
7. 길드 가입이 필요한 경우 Discord `/guilds/{guild_id}/members/{user_id}`에 `PUT`. 봇 토큰 사용.

OAuth scope는 최소화한다. 필요한 scope만 요청하고, `email`은 진짜 필요할 때만.

> Discord OAuth 클라이언트 라이브러리는 미정. 결정되면 본 파일에 명시하고 구현 위치(`app/domains/auth/discord_client.py` 등)도 함께 적는다.

## 자체 JWT

- 알고리즘: `HS256`. 키 교체가 잦으면 `RS256`로 재검토.
- 페이로드: `sub`(우리 user id), `discord_id`, `exp`, `iat`, `jti`. 그 외 필드 금지.
- 만료: access 30분, refresh 30일. 두 토큰은 별도로 발급/검증한다.
- 검증은 `app/core/security.py`의 `get_current_user` 의존성을 통해서만 수행한다. 라우터·Service에서 `jwt.decode` 직접 호출 금지.

## 비밀 관리

- 모든 비밀(`JWT_SECRET`, `DISCORD_CLIENT_SECRET`, `DISCORD_BOT_TOKEN`)은 `Settings`에서 `SecretStr`로 받는다.
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

- 봇 토큰은 절대 클라이언트에 노출되지 않는다. 길드 가입 등 봇 API 호출은 서버에서만 수행한다.
- 봇 토큰을 사용하는 함수는 `app/core/discord.py` 또는 `app/domains/discord/`에 격리한다.

## Rate limit

- Discord API `429` 응답은 외부 클라이언트 래퍼에서 처리한다 (`Retry-After` 헤더 준수).
- Service는 rate limit을 모른다. 재시도 정책은 클라이언트 계층의 책임.

## 입력 검증

- 모든 요청 본문은 Pydantic 스키마로 받는다. `request.json()`을 직접 호출하지 않는다.
- 외부에서 받은 ID(특히 Discord ID)는 그대로 SQL 조건에 넣어도 안전하다 (ORM이 파라미터화). 단, 로그에 출력할 때는 화이트리스트 검증.