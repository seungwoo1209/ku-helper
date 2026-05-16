from httpx_oauth.clients.discord import DiscordOAuth2
from httpx_oauth.exceptions import GetProfileError
from httpx_oauth.oauth2 import GetAccessTokenError

from app.core.config import Settings
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
from app.domains.auth.schemas import TokenRead
from app.domains.users.repository import UserRepository


class AuthService:
    def __init__(
        self,
        oauth_client: DiscordOAuth2,
        user_repository: UserRepository,
        settings: Settings,
    ) -> None:
        self._oauth = oauth_client
        self._users = user_repository
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

        # 4. User upsert (유일한 DB 쓰기).
        user = await self._users.upsert_by_discord_id(discord_id, discord_username)

        # 5. 자체 JWT 발급.
        return TokenRead(
            access_token=create_access_token(user.id, user.discord_id),
            refresh_token=create_refresh_token(user.id, user.discord_id),
        )
