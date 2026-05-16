from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.domains.auth.dependencies import get_auth_service
from app.domains.auth.schemas import TokenRead
from app.domains.auth.service import AuthService

router = APIRouter(prefix="/auth/discord", tags=["auth"])


@router.get(
    "/login",
    response_class=RedirectResponse,
    status_code=307,
)
async def login(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> RedirectResponse:
    """Discord 인가 페이지로 사용자를 리다이렉트한다."""
    return RedirectResponse(
        url=await service.build_login_url(),
        status_code=307,
    )


@router.get("/callback", response_model=TokenRead, status_code=200)
async def callback(
    code: Annotated[str, Query(...)],
    state: Annotated[str, Query(...)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenRead:
    """Discord OAuth 콜백을 처리하고 자체 JWT를 발급한다."""
    return await service.handle_callback(code, state)
