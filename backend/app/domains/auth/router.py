from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import RedirectResponse, Response

from app.core.config import Settings, get_settings
from app.domains.auth.dependencies import get_auth_service
from app.domains.auth.schemas import LogoutRequest, TokenRead, TokenRefreshRequest
from app.domains.auth.service import AuthService

# backend/app/domains/auth/router.py 기준 3단계 위 = backend/ → backend/docs/endpoints
_DOCS_DIR = Path(__file__).resolve().parents[3] / "docs" / "endpoints"

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/discord/login",
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
    "/discord/callback",
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


@router.post(
    "/refresh",
    response_model=TokenRead,
    status_code=200,
    summary="Access 토큰 갱신 (F-05)",
    description=(
        "유효한 refresh JWT 를 받아 새 access·refresh 쌍을 발급한다. 기존 refresh jti 는 "
        "Redis whitelist 에서 즉시 제거되므로(rotation) 한 번 사용된 refresh 토큰은 두 번째 "
        "호출에서 401 을 받는다.\n\n"
        "본 엔드포인트는 인증 헤더가 아니라 본문의 `refresh_token` 으로만 인증한다. "
        "Access 토큰이 만료된 상태에서도 호출 가능하도록 의도된 설계."
    ),
    response_description="새 access·refresh JWT 쌍",
    responses={
        401: {
            "description": (
                "refresh JWT 가 위조·만료됐거나 jti 가 whitelist 에 없음 "
                "(INVALID_AUTH_TOKEN)"
            ),
        },
    },
)
async def refresh(
    body: TokenRefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenRead:
    """refresh JWT 검증 + rotation 후 새 토큰 쌍 반환."""
    return await service.refresh_tokens(body.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃 (F-02)",
    description=(
        "refresh JWT 의 jti 를 Redis whitelist 에서 제거한다. 이후 같은 refresh 로 "
        "/auth/refresh 호출 시 401. 같은 토큰으로 두 번 호출해도 204 (DEL 은 idempotent).\n\n"
        "Access 토큰은 별도 블랙리스트가 없으므로 만료(30분) 시까지 유효하게 남는다. 즉시 "
        "차단이 필요하면 클라이언트에서 access 토큰을 폐기한다."
    ),
    response_description="본문 없음",
    responses={
        401: {
            "description": "refresh JWT 가 위조·만료된 경우 (INVALID_AUTH_TOKEN)",
        },
    },
)
async def logout(
    body: LogoutRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    """refresh jti 를 whitelist 에서 제거."""
    await service.logout(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
