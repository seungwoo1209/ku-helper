from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domains.auth.dependencies import get_auth_service
from app.domains.auth.schemas import LoginUrlRead, TokenRead
from app.domains.auth.service import AuthService

router = APIRouter(prefix="/auth/discord", tags=["auth"])


@router.get("/login", response_model=LoginUrlRead, status_code=200)
async def login(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginUrlRead:
    """Discord 인증 URL과 서명된 state를 발급한다."""
    return await service.build_login_url()


@router.get("/callback", response_model=TokenRead, status_code=200)
async def callback(
    code: Annotated[str, Query(...)],
    state: Annotated[str, Query(...)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenRead:
    """Discord OAuth 콜백을 처리하고 자체 JWT를 발급한다."""
    return await service.handle_callback(code, state)
