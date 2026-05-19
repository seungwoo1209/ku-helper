from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import RedirectResponse

from app.core.config import Settings, get_settings
from app.domains.auth.dependencies import get_auth_service
from app.domains.auth.service import AuthService

# backend/app/domains/auth/router.py 기준 3단계 위 = backend/ → backend/docs/endpoints
_DOCS_DIR = Path(__file__).resolve().parents[3] / "docs" / "endpoints"

router = APIRouter(prefix="/auth/discord", tags=["auth"])


@router.get(
    "/login",
    response_class=RedirectResponse,
    status_code=307,
    summary="Discord 로그인 시작",
    description=(
        "Discord 인가 페이지로 사용자를 307 리다이렉트한다. "
        "scope = `identify`, `applications.commands`. `applications.commands` 는 "
        "user-install (`integration_type=1`) 을 자동 성립시켜 mutual guild 가 없는 "
        "사용자에게도 DM 발송이 가능하도록 한다(Discord 에러 50278 회피).\n\n"
        "서버는 5분 만료 state JWT 를 발급해 인가 URL 의 `state` 파라미터로 함께 보낸다. "
        "콜백에서 state 가 검증된다."
    ),
    response_description="Discord 인가 페이지로의 307 리다이렉트",
)
async def login(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> RedirectResponse:
    """Discord 인가 페이지로 사용자를 리다이렉트한다."""
    return RedirectResponse(
        url=await service.build_login_url(),
        status_code=307,
    )


@router.get(
    "/callback",
    response_class=RedirectResponse,
    status_code=307,
    summary="Discord OAuth 콜백",
    description=(_DOCS_DIR / "callback.md").read_text(encoding="utf-8"),
    response_description=(
        "프론트엔드(`Settings.frontend_url`)로의 307 리다이렉트. "
        "쿼리에 `access_token` 과 `refresh_token` 포함."
    ),
    responses={
        401: {
            "description": "state 위조 또는 만료 (INVALID_OAUTH_STATE)",
        },
        502: {
            "description": (
                "Discord 토큰 교환 실패 (DISCORD_TOKEN_EXCHANGE_FAILED) 또는 "
                "Discord 사용자 정보 조회 실패 (DISCORD_USER_FETCH_FAILED)"
            ),
        },
    },
)
async def callback(
    code: Annotated[str, Query(...)],
    state: Annotated[str, Query(...)],
    background_tasks: BackgroundTasks,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """Discord OAuth 콜백을 처리하고 프론트엔드로 토큰과 함께 리다이렉트한다."""
    result = await service.handle_callback(code, state)
    background_tasks.add_task(
        service.maybe_send_welcome_dm, result.discord_id, result.is_new_user
    )
    redirect_url = (
        f"{settings.frontend_url}/"
        f"?access_token={result.token.access_token}"
        f"&refresh_token={result.token.refresh_token}"
    )
    return RedirectResponse(url=redirect_url, status_code=307)
