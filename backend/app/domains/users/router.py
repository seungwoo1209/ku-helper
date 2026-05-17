from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.security import get_current_user
from app.domains.users.models import User
from app.domains.users.schemas import UserRead, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserRead, status_code=200)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    """현재 로그인한 사용자 정보를 반환한다."""
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead, status_code=200)
async def update_me(
    body: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    """현재 사용자 정보를 수정한다. (미구현)"""
    raise NotImplementedError("PATCH /users/me 미구현")


@router.delete("/me", status_code=204, response_class=Response)
async def delete_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """현재 사용자 계정을 삭제한다 (서비스 탈퇴). (미구현)"""
    raise NotImplementedError("DELETE /users/me 미구현")
