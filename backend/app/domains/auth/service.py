import structlog
from httpx_oauth.clients.discord import DiscordOAuth2
from httpx_oauth.exceptions import GetProfileError
from httpx_oauth.oauth2 import GetAccessTokenError

from app.core.config import Settings
from app.core.discord import DiscordBotApiError, DiscordBotClient
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_state_token,
    verify_state_token,
)
from app.domains.auth.exceptions import (
    DiscordTokenExchangeFailed,
    DiscordUserFetchFailed,
    InvalidOAuthState,
)
from app.domains.auth.schemas import LoginUrlRead, TokenRead
from app.domains.users.repository import UserRepository

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(
        self,
        oauth_client: DiscordOAuth2,
        bot_client: DiscordBotClient,
        user_repository: UserRepository,
        settings: Settings,
    ) -> None:
        self._oauth = oauth_client
        self._bot = bot_client
        self._users = user_repository
        self._settings = settings

    async def build_login_url(self) -> LoginUrlRead:
        state = create_state_token()
        url = await self._oauth.get_authorization_url(
            redirect_uri=self._settings.discord_redirect_uri,
            state=state,
            scope=self._settings.discord_oauth_scopes,
        )
        return LoginUrlRead(authorization_url=url, state=state)

    async def handle_callback(self, code: str, state: str) -> TokenRead:
        # 1. state 검증.
        try:
            verify_state_token(state)
        except Exception as exc:
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

        # 4. 길드 가입 (베스트 에포트: 실패해도 로그인은 성공).
        try:
            await self._bot.add_guild_member(discord_id, access_token)
        except DiscordBotApiError:
            logger.warning(
                "discord_guild_join_failed",
                discord_id=discord_id,
                guild_id=self._settings.discord_guild_id,
            )

        # 5. User upsert (유일한 DB 쓰기).
        user = await self._users.upsert_by_discord_id(discord_id, discord_username)

        # 6. 자체 JWT 발급.
        return TokenRead(
            access_token=create_access_token(user.id, user.discord_id),
            refresh_token=create_refresh_token(user.id, user.discord_id),
        )
