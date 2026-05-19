from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LunchDispatchResponse(BaseModel):
    """`POST /me/immediate-send/lunch` 의 202 응답.

    API 는 큐 테이블 (`immediate_send_requests`) 에 한 줄을 INSERT 하고 즉시 반환한다.
    실제 학식·맛집 조회와 Discord DM 발송은 봇 컨테이너의 폴링 잡(5초 간격)이 수행.
    클라이언트는 `request_id` 로 후속 상태 조회를 할 수 있다(상태 엔드포인트는 후속).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "request_id": 17,
                    "requested_at": "2026-05-20T11:25:30+00:00",
                }
            ]
        },
    )

    request_id: int = Field(
        description="큐 적재 row 의 PK. 후속 상태 조회·로그 추적용.",
        examples=[17],
    )
    requested_at: datetime = Field(
        description="서버가 요청을 INSERT 한 시각 (ISO 8601, UTC).",
    )
