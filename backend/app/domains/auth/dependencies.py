from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends, Request
from httpx_oauth.clients.discord import DiscordOAuth2
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.discord import DiscordBotClient
from app.domains.auth.service import AuthService
from app.domains.users.dependencies import get_user_repository
from app.domains.users.repository import UserRepository


@lru_cache
def _get_oauth_client_cached(
    client_id: str,
    client_secret: str,
    scopes_key: tuple[str, ...],
) -> DiscordOAuth2:
    return DiscordOAuth2(
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(scopes_key),
    )


def get_oauth_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiscordOAuth2:
    return _get_oauth_client_cached(
        settings.discord_client_id,
        settings.discord_client_secret.get_secret_value(),
        tuple(settings.discord_oauth_scopes),
    )


def get_http_client(request: Request) -> httpx.AsyncClient:
    # 라이프스팬에서 생성된 공유 httpx 클라이언트.
    return request.app.state.http_client  # type: ignore[no-any-return]


def get_redis(request: Request) -> Redis:
    # 라이프스팬에서 생성된 공유 redis 클라이언트.
    return request.app.state.redis  # type: ignore[no-any-return]


def get_discord_bot_client(
    http_client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiscordBotClient:
    return DiscordBotClient(http_client, settings)


def get_auth_service(
    oauth_client: Annotated[DiscordOAuth2, Depends(get_oauth_client)],
    bot_client: Annotated[DiscordBotClient, Depends(get_discord_bot_client)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(oauth_client, bot_client, user_repository, redis, settings)
