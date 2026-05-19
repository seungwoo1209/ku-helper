from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.domains.immediate_send.dependencies import get_immediate_send_service
from app.domains.immediate_send.schemas import LunchDispatchResponse
from app.domains.immediate_send.service import ImmediateSendService
from app.domains.users.models import User

router = APIRouter(prefix="/me/immediate-send", tags=["immediate-send"])


@router.post("/lunch", response_model=LunchDispatchResponse, status_code=202)
async def dispatch_lunch_now(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ImmediateSendService, Depends(get_immediate_send_service)],
) -> LunchDispatchResponse:
    """즉시 점심 DM 발송 요청을 큐에 적재한다.

    봇 컨테이너의 폴링 잡이 5초 간격으로 픽업해 학식·맛집 데이터를 조회한 뒤
    Discord DM 으로 발송한다. 응답은 202 + 적재된 request_id."""
    request = await service.request_lunch_dispatch(current_user)
    return LunchDispatchResponse(
        request_id=request.id, requested_at=request.requested_at
    )
