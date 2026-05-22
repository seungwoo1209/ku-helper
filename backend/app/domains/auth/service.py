from dataclasses import dataclass

import structlog
from httpx_oauth.clients.discord import DiscordOAuth2
from httpx_oauth.exceptions import GetProfileError
from httpx_oauth.oauth2 import GetAccessTokenError
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.discord import DiscordBotApiError, DiscordBotClient
from app.core.security import (
    InvalidAuthToken,
    TokenType,
    assert_refresh_jti_active,
    consume_state_jti,
    create_access_token,
    create_refresh_token,
    create_state_token,
    decode_token,
    register_refresh_jti,
    revoke_refresh_jti,
    verify_state_token,
)
from app.domains.auth.exceptions import (
    DiscordTokenExchangeFailed,
    DiscordUserFetchFailed,
    InvalidOAuthState,
)
from app.domains.auth.schemas import TokenRead
from app.domains.users.repository import UserRepository

logger = structlog.get_logger(__name__)

_WELCOME_MESSAGE = "👋 ku-helper에 가입하셨어요! 알림 설정은 대시보드에서 해주세요."


@dataclass(frozen=True, slots=True)
class AuthCallbackResult:
    token: TokenRead
    discord_id: int
    is_new_user: bool


class AuthService:
    def __init__(
        self,
        oauth_client: DiscordOAuth2,
        bot_client: DiscordBotClient,
        user_repository: UserRepository,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._oauth = oauth_client
        self._bot = bot_client
        self._users = user_repository
        self._redis = redis
        self._settings = settings

    async def build_login_url(self) -> str:
        state = create_state_token()
        return await self._oauth.get_authorization_url(
            redirect_uri=self._settings.discord_redirect_uri,
            state=state,
            scope=self._settings.discord_oauth_scopes,
            extras_params={
                "integration_type": self._settings.discord_integration_type,
                # 이미 동일 scope로 인가한 사용자는 동의 화면 없이 바로 콜백.
                "prompt": "none",
            },
        )

    async def handle_callback(self, code: str, state: str) -> AuthCallbackResult:
        # 1. state 검증 + 1회용 잠금. JWT 서명·만료 검증을 통과하더라도 같은 jti 로
        # 다시 콜백이 오면 InvalidAuthToken → InvalidOAuthState 로 재포장한다.
        try:
            payload = verify_state_token(state)
            state_jti = str(payload["jti"])
        except (InvalidAuthToken, KeyError, TypeError) as exc:
            raise InvalidOAuthState() from exc
        try:
            await consume_state_jti(self._redis, state_jti)
        except InvalidAuthToken as exc:
            raise InvalidOAuthState() from exc

        # 2. 토큰 교환.
        try:
            token = await self._oauth.get_access_token(
                code, self._settings.discord_redirect_uri
            )
        except GetAccessTokenError as exc:
            raise DiscordTokenExchangeFailed() from exc
        access_token = token["access_token"]

        # 3. /users/@me 호출 (httpx-oauth가 처리).
        try:
            profile = await self._oauth.get_profile(access_token)
        except GetProfileError as exc:
            raise DiscordUserFetchFailed() from exc
        try:
            discord_id = int(profile["id"])
            discord_username = str(profile["username"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DiscordUserFetchFailed() from exc

        # 4. User upsert (유일한 DB 쓰기). created=True면 신규 가입.
        user, created = await self._users.upsert_by_discord_id(
            discord_id, discord_username
        )

        # 5. 자체 JWT 발급 + refresh jti 를 Redis whitelist 에 등록.
        refresh_token, refresh_jti = create_refresh_token(user.id, user.discord_id)
        await register_refresh_jti(self._redis, refresh_jti, user.id)

        return AuthCallbackResult(
            token=TokenRead(
                access_token=create_access_token(user.id, user.discord_id),
                refresh_token=refresh_token,
            ),
            discord_id=user.discord_id,
            is_new_user=created,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenRead:
        """Refresh JWT 검증 + rotation. old jti DEL → 새 access/refresh 발급 + new jti SET."""
        payload = decode_token(refresh_token, TokenType.REFRESH)
        old_jti = str(payload["jti"])
        try:
            user_id = int(payload["sub"])
            discord_id = int(payload["discord_id"])
        except (KeyError, TypeError, ValueError) as exc:
            # decode_token 통과 후 payload 형상이 어긋난 케이스 — 무효 처리.
            raise InvalidAuthToken() from exc

        await assert_refresh_jti_active(self._redis, old_jti)
        await revoke_refresh_jti(self._redis, old_jti)

        new_refresh_token, new_jti = create_refresh_token(user_id, discord_id)
        await register_refresh_jti(self._redis, new_jti, user_id)

        return TokenRead(
            access_token=create_access_token(user_id, discord_id),
            refresh_token=new_refresh_token,
        )

    async def logout(self, refresh_token: str) -> None:
        """Refresh jti 를 whitelist 에서 제거. 이미 없어도 idempotent."""
        payload = decode_token(refresh_token, TokenType.REFRESH)
        jti = str(payload["jti"])
        await revoke_refresh_jti(self._redis, jti)

    async def maybe_send_welcome_dm(self, discord_id: int, is_new_user: bool) -> None:
        # 신규 가입자에게만 1회 환영 DM. 실패는 베스트 에포트.
        if not is_new_user:
            logger.debug("welcome_dm_skipped_existing_user", discord_id=discord_id)
            return
        logger.info("welcome_dm_attempt", discord_id=discord_id)
        try:
            await self._bot.send_dm(discord_id, _WELCOME_MESSAGE)
        except DiscordBotApiError:
            # send_dm 내부에서 logger.exception을 이미 남기지만,
            # 환영 흐름의 베스트 에포트 결과를 한 줄로 표시해 둔다.
            logger.warning("welcome_dm_failed", discord_id=discord_id)
            return
        logger.info("welcome_dm_succeeded", discord_id=discord_id)
