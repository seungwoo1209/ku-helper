from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.domains.users.dependencies import get_current_user, get_user_service
from app.domains.users.models import User
from app.domains.users.schemas import UserRead, UserUpdate
from app.domains.users.service import UserService

router = APIRouter()


_AUTH_401 = {
    "description": "JWT 누락·만료·서명오류 또는 USER_DELETED",
}


@router.get(
    "/me",
    response_model=UserRead,
    status_code=200,
    summary="내 정보 조회",
    description=(
        "현재 로그인한 사용자의 프로필을 반환한다. JWT access 토큰이 필요하며, "
        "탈퇴(`status=DELETED`) 상태의 사용자는 401 `USER_DELETED` 로 차단된다."
    ),
    response_description="현재 로그인 사용자 프로필",
    responses={401: _AUTH_401},
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    """현재 로그인한 사용자 정보를 반환한다."""
    return UserRead.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    status_code=200,
    summary="내 정보 수정 (미구현)",
    description=(
        "정책 미결로 현재 미구현이다 (backend roadmap A-1). 호출 시 서버 내부에서 "
        "`NotImplementedError` 가 발생해 500 으로 전달된다. 수정 가능 필드가 정의되면 "
        "본 엔드포인트가 채워질 예정."
    ),
    response_description="(미구현) 수정된 사용자 프로필",
    responses={
        401: _AUTH_401,
        501: {"description": "현재 미구현 — 수정 가능 필드 정책 미결"},
    },
)
async def update_me(
    body: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    """현재 사용자 정보를 수정한다. (미구현)"""
    raise NotImplementedError("PATCH /users/me 미구현")


@router.delete(
    "/me",
    status_code=204,
    response_class=Response,
    summary="내 계정 삭제",
    description=(
        "**소프트 삭제**. `User.status` 를 `DELETED` 로 전환하고, 같은 트랜잭션에서 "
        "해당 사용자의 알림 설정과 발송 이력을 **물리 삭제** 한다 (개인정보 최소화). "
        "동일 Discord 계정이 재로그인하면 같은 레코드의 status 가 `ACTIVE` 로 복귀한다 "
        "(환영 DM 은 재발송되지 않음). 기존 access 토큰은 다음 요청에서 401 `USER_DELETED` "
        "로 자동 무효화된다."
    ),
    response_description="삭제 완료. 본문 없음",
    responses={401: _AUTH_401},
)
async def delete_me(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> Response:
    """현재 사용자 계정을 삭제(소프트 삭제)한다."""
    await service.delete_account(current_user)
    return Response(status_code=204)
