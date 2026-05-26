from typing import Annotated

from fastapi import APIRouter, Depends

from app.domains.immediate_send.dependencies import get_immediate_send_service
from app.domains.users.dependencies import get_current_user
from app.domains.immediate_send.schemas import (
    LibraryDispatchRequest,
    LibraryDispatchResponse,
    LunchDispatchResponse,
    TransitDispatchRequest,
    TransitDispatchResponse,
)
from app.domains.immediate_send.service import ImmediateSendService
from app.domains.users.models import User

router = APIRouter(prefix="/me/immediate-send", tags=["immediate-send"])


@router.post(
    "/lunch",
    response_model=LunchDispatchResponse,
    status_code=202,
    summary="즉시 점심 DM 발송 요청",
    description=(
        "현재 사용자에게 즉시 점심 DM 을 보내달라는 요청을 큐 테이블 "
        "(`immediate_send_requests`) 에 INSERT 하고 202 로 즉시 반환한다.\n\n"
        "**처리 흐름**: 봇 컨테이너가 5초 간격으로 큐를 폴링 → pending 행을 픽업 → "
        "학식·맛집 데이터 크롤 → Discord DM 발송 → 큐 상태 업데이트.\n\n"
        "**쿨다운**: 동일 사용자의 미처리 요청이 큐에 남아 있으면 429 "
        "`IMMEDIATE_SEND_RATE_LIMITED` 로 거절된다. 이후 상태 조회 엔드포인트는 후속."
    ),
    response_description="큐 적재 결과 (request_id, requested_at)",
    responses={
        401: {"description": "JWT 누락·만료·서명오류 또는 USER_DELETED"},
        429: {
            "description": "동일 사용자의 처리 대기 요청이 이미 큐에 존재 (IMMEDIATE_SEND_RATE_LIMITED)",
        },
    },
)
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


@router.post(
    "/transit",
    response_model=TransitDispatchResponse,
    status_code=202,
    summary="즉시 교통 DM 발송 요청",
    description=(
        "현재 사용자에게 지정한 역·호선의 지하철 도착 정보 DM 을 즉시 보내달라는 요청을 "
        "큐 테이블 (`immediate_send_requests`) 에 INSERT 하고 202 로 즉시 반환한다.\n\n"
        "**처리 흐름**: 봇 컨테이너가 5초 간격으로 큐를 폴링 → pending 행을 픽업 → "
        "서울 공공 API 로 실시간 도착 조회 → Discord DM 발송 → 큐 상태 업데이트.\n\n"
        "**인증 필요**: `Authorization: Bearer <access>` 헤더. 401 사유는 `INVALID_TOKEN` "
        "또는 `USER_DELETED`.\n\n"
        "**쿨다운**: 동일 사용자의 미처리 요청이 큐에 남아 있으면 429 "
        "`IMMEDIATE_SEND_RATE_LIMITED` 로 거절된다. 이후 상태 조회 엔드포인트는 후속."
    ),
    response_description="큐 적재 결과 (request_id, requested_at)",
    responses={
        401: {"description": "JWT 누락·만료·서명오류 또는 USER_DELETED"},
        422: {"description": "station_name·line 형식 검증 실패"},
        429: {
            "description": "동일 사용자의 처리 대기 요청이 이미 큐에 존재 (IMMEDIATE_SEND_RATE_LIMITED)",
        },
    },
)
async def dispatch_transit_now(
    body: TransitDispatchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ImmediateSendService, Depends(get_immediate_send_service)],
) -> TransitDispatchResponse:
    """즉시 교통 DM 발송 요청을 큐에 적재한다.

    봇 컨테이너의 폴링 잡이 5초 간격으로 픽업해 서울 공공 API 로 도착 정보를 조회한 뒤
    Discord DM 으로 발송한다. 응답은 202 + 적재된 request_id."""
    request = await service.request_transit_dispatch(current_user, body)
    return TransitDispatchResponse(
        request_id=request.id, requested_at=request.requested_at
    )


@router.post(
    "/library",
    response_model=LibraryDispatchResponse,
    status_code=202,
    summary="즉시 도서관 좌석 DM 발송 요청",
    description=(
        "현재 사용자에게 지정한 열람실의 현재 잔여 좌석 DM 을 즉시 보내달라는 요청을 "
        "큐 테이블 (`immediate_send_requests`) 에 INSERT 하고 202 로 즉시 반환한다.\n\n"
        "**처리 흐름**: 봇 컨테이너가 5초 간격으로 큐를 폴링 → pending 행을 픽업 → "
        "도서관 좌석 API 조회 → Discord DM 발송 → 큐 상태 업데이트.\n\n"
        "**임계값 없음**: 즉시 발송은 1회성 현재 스냅샷이라 정기 알림의 임계값(F-13)·"
        "긴급 표시(F-15)는 적용되지 않는다. `reading_room_id=0` 은 전체 열람실 합산이다.\n\n"
        "**인증 필요**: `Authorization: Bearer <access>` 헤더. 401 사유는 `INVALID_TOKEN` "
        "또는 `USER_DELETED`.\n\n"
        "**쿨다운**: 동일 사용자의 미처리 요청이 큐에 남아 있으면 429 "
        "`IMMEDIATE_SEND_RATE_LIMITED` 로 거절된다. 이후 상태 조회 엔드포인트는 후속."
    ),
    response_description="큐 적재 결과 (request_id, requested_at)",
    responses={
        401: {"description": "JWT 누락·만료·서명오류 또는 USER_DELETED"},
        422: {"description": "reading_room_id 가 0·1·2·3·5 외 값(예: 4)"},
        429: {
            "description": "동일 사용자의 처리 대기 요청이 이미 큐에 존재 (IMMEDIATE_SEND_RATE_LIMITED)",
        },
    },
)
async def dispatch_library_now(
    body: LibraryDispatchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ImmediateSendService, Depends(get_immediate_send_service)],
) -> LibraryDispatchResponse:
    """즉시 도서관 좌석 DM 발송 요청을 큐에 적재한다.

    봇 컨테이너의 폴링 잡이 5초 간격으로 픽업해 도서관 좌석 API 로 현재 잔여석을 조회한 뒤
    Discord DM 으로 발송한다. 응답은 202 + 적재된 request_id."""
    request = await service.request_library_dispatch(current_user, body)
    return LibraryDispatchResponse(
        request_id=request.id, requested_at=request.requested_at
    )
