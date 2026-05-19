from dataclasses import dataclass

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
        settings: Settings,
    ) -> None:
        self._oauth = oauth_client
        self._bot = bot_client
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

    async def handle_callback(self, code: str, state: str) -> AuthCallbackResult:
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

        # 4. User upsert (유일한 DB 쓰기). created=True면 신규 가입.
        user, created = await self._users.upsert_by_discord_id(
            discord_id, discord_username
        )

        # 5. 자체 JWT 발급 + 결과 패키징.
        return AuthCallbackResult(
            token=TokenRead(
                access_token=create_access_token(user.id, user.discord_id),
                refresh_token=create_refresh_token(user.id, user.discord_id),
            ),
            discord_id=user.discord_id,
            is_new_user=created,
        )

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
