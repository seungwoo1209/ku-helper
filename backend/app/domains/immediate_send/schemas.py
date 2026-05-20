from datetime import datetime
from typing import Literal

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


class TransitDispatchRequest(BaseModel):
    """`POST /me/immediate-send/transit` 의 요청 body.

    F-07 정기 교통 알림과 동일한 두 필수 키 (`station_name`, `line`) 만 받는다.
    즉시 발송은 1회성이라 정기 알림의 활성 시간대(`start_time`/`end_time`)·반복 주기
    (`repeat_interval_minutes`) 는 의미가 없어 받지 않는다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"station_name": "강남", "line": "2호선"},
            ]
        },
    )

    station_name: str = Field(
        min_length=1,
        max_length=50,
        description=(
            "서울 지하철 역 이름 (한글). 봇이 서울 공공 API 의 `stationName` 파라미터로 그대로 전달하므로 "
            "공공 API 의 역명 표기와 일치해야 한다."
        ),
        examples=["강남"],
    )
    line: str = Field(
        min_length=1,
        max_length=20,
        description=(
            "호선 표기. '2호선', '경의중앙선' 등 한글 표기 그대로. 봇이 임베드 title·필터 표현에 사용한다."
        ),
        examples=["2호선"],
    )


class TransitDispatchResponse(BaseModel):
    """`POST /me/immediate-send/transit` 의 202 응답.

    API 는 큐 테이블 (`immediate_send_requests`) 에 한 줄을 INSERT 하고 즉시 반환한다.
    실제 도착 정보 조회와 Discord DM 발송은 봇 컨테이너의 폴링 잡(5초 간격)이 수행.
    `LunchDispatchResponse` 와 응답 포맷은 동일하지만 도메인 의미가 다르므로 별도 모델로 둔다.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "request_id": 42,
                    "requested_at": "2026-05-20T11:25:30+00:00",
                }
            ]
        },
    )

    request_id: int = Field(
        description="큐 적재 row 의 PK. 후속 상태 조회·로그 추적용.",
        examples=[42],
    )
    requested_at: datetime = Field(
        description="서버가 요청을 INSERT 한 시각 (ISO 8601, UTC).",
        examples=["2026-05-20T11:25:30+00:00"],
    )


class LibraryDispatchRequest(BaseModel):
    """`POST /me/immediate-send/library` 의 요청 body.

    "지금 이 열람실 잔여 좌석을 알려줘" 1회성 요청이다. 임계값 알림(F-13)·중복 방지
    (F-14)·긴급 표시(F-15)는 정기 알림 설정에서 다루고, 즉시 발송은 현재 스냅샷만
    보내므로 `reading_room_id` 하나만 받는다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"reading_room_id": 1},
            ]
        }
    )

    reading_room_id: Literal[0, 1, 2, 3, 5] = Field(
        description=(
            "대상 열람실 번호. 0·1·2·3·5 중 하나. 0 은 전체 열람실 잔여석 합산, "
            "1·2·3·5 는 개별 열람실(제4열람실 미운영). 분리 운영되는 제1·제3열람실과 "
            "0(전체)은 봇이 A/B 좌석을 합산해 계산한다. 정기 알림의 `LibraryConfig` 와 "
            "동일한 의미다."
        ),
        examples=[1],
    )


class LibraryDispatchResponse(BaseModel):
    """`POST /me/immediate-send/library` 의 202 응답.

    API 는 큐 테이블 (`immediate_send_requests`) 에 한 줄을 INSERT 하고 즉시 반환한다.
    실제 좌석 조회와 Discord DM 발송은 봇 컨테이너의 폴링 잡(5초 간격)이 수행.
    `Lunch/TransitDispatchResponse` 와 응답 포맷은 동일하지만 도메인 의미가 달라 별도 모델로 둔다.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "request_id": 53,
                    "requested_at": "2026-05-21T02:10:00+00:00",
                }
            ]
        },
    )

    request_id: int = Field(
        description="큐 적재 row 의 PK. 후속 상태 조회·로그 추적용.",
        examples=[53],
    )
    requested_at: datetime = Field(
        description="서버가 요청을 INSERT 한 시각 (ISO 8601, UTC).",
        examples=["2026-05-21T02:10:00+00:00"],
    )
