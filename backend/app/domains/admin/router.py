from typing import Annotated

from fastapi import APIRouter, Depends

from app.domains.admin.schemas import AdminHealthRead
from app.domains.users.dependencies import require_role
from app.domains.users.models import User, UserRole

router = APIRouter()


_AUTH_401 = {
    "description": "JWT 누락·만료·서명오류 또는 USER_DELETED",
}
_FORBIDDEN_403 = {
    "description": "ADMIN 권한이 없는 사용자 — `code=NOT_AUTHORIZED_FOR_ROLE`",
}


@router.get(
    "/health",
    response_model=AdminHealthRead,
    status_code=200,
    summary="관리자 헬스 체크",
    description=(
        "`require_role(UserRole.ADMIN)` 가드 동작 확인용 엔드포인트. 관리자 권한이 있는 "
        '사용자에게는 `{"status": "ok"}` 를 반환하고, 일반 사용자는 403 '
        "`NOT_AUTHORIZED_FOR_ROLE` 로 차단된다. 향후 F-23 관리자 대시보드 엔드포인트들의 "
        "권한 가드가 모두 이 패턴을 따른다. "
        "인증 필요: `Authorization: Bearer <access>` 헤더. 토큰 누락·만료·서명오류 또는 "
        "탈퇴(`USER_DELETED`) 사용자는 401."
    ),
    response_description="권한 검증 통과 시 상태 ping",
    responses={401: _AUTH_401, 403: _FORBIDDEN_403},
)
async def get_admin_health(
    admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> AdminHealthRead:
    """관리자 권한 가드 진입점."""
    return AdminHealthRead(status="ok")
