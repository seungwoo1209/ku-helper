from datetime import datetime, time
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.notifications.models import NotificationType


# ---------------------------------------------------------------------------
# Transit (F-06, F-07, F-08)
# ---------------------------------------------------------------------------


class _TransitArrival(BaseModel):
    """F-06 단발 도착 알림: 특정 시각에 N분 전 1회만 발송한다.

    `_TransitCreate` 의 `config` 필드로 wrap 되어 외부에 노출된다. 단독으로
    클라이언트가 다루지 않는다.
    """

    mode: Literal["arrival"] = Field(
        description="단발 모드 식별자. 'arrival' 은 도착 N 분 전 1회 발송.",
    )
    station_name: str = Field(
        min_length=1,
        max_length=50,
        description="서울 지하철 역 이름(한글). 공공 API 의 역명과 동일해야 매칭된다.",
        examples=["성신여대입구"],
    )
    line: str = Field(
        min_length=1,
        max_length=20,
        description="호선 한글 표기. '4호선', '경의중앙선' 등.",
        examples=["4호선"],
    )
    minutes_before: int = Field(
        ge=1,
        le=120,
        description="도착 N 분 전 알림. 1~120 분.",
        examples=[10],
    )
    include_congestion: bool = Field(
        default=True,
        description="혼잡도 정보 포함 여부. 공공 API 가 제공할 때만 유효.",
    )


class _TransitRecurring(BaseModel):
    """F-07 정기 간격 알림: 시작·종료 시각 사이 N분마다 반복 발송한다.

    `_TransitCreate` 의 `config` 필드로 wrap 되어 외부에 노출된다.
    """

    mode: Literal["recurring"] = Field(
        description="정기 모드 식별자. 'recurring' 은 시간대 내 N 분 간격 반복.",
    )
    station_name: str = Field(
        min_length=1,
        max_length=50,
        description="서울 지하철 역 이름(한글). 공공 API 의 역명과 동일.",
        examples=["성신여대입구"],
    )
    line: str = Field(
        min_length=1,
        max_length=20,
        description="호선 한글 표기.",
        examples=["4호선"],
    )
    start_time: time = Field(
        description="반복 시작 시각 (24h 'HH:MM' 또는 'HH:MM:SS'). 서버 로컬 시간.",
        examples=["08:00:00"],
    )
    end_time: time = Field(
        description="반복 종료 시각. `start_time` 보다 늦어야 한다 (validator).",
        examples=["10:00:00"],
    )
    repeat_interval_minutes: int = Field(
        ge=1,
        le=180,
        description="반복 간격(분). 1~180 분.",
        examples=[5],
    )
    include_congestion: bool = Field(
        default=True,
        description="혼잡도 정보 포함 여부.",
    )

    @model_validator(mode="after")
    def _start_before_end(self) -> "_TransitRecurring":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


TransitConfig = Annotated[
    Union[_TransitArrival, _TransitRecurring],
    Field(discriminator="mode"),
]


# ---------------------------------------------------------------------------
# Lunch (F-09, F-10, F-11, F-12)
# ---------------------------------------------------------------------------


class LunchConfig(BaseModel):
    """점심 알림 설정. 지정 시각에 학식 메뉴와 추천 맛집을 DM 으로 전달한다."""

    notify_at: time = Field(
        description="알림 발송 시각 (24h). 보통 점심 30~60 분 전을 권장.",
        examples=["11:00:00"],
    )
    max_price: int | None = Field(
        default=None,
        ge=0,
        description="맛집 추천에 적용할 1 인 기준 최대 가격(원). null 이면 제한 없음.",
        examples=[12000],
    )
    recommend_count: int = Field(
        default=3,
        ge=1,
        le=10,
        description="맛집 추천 개수(1~10). 학식 메뉴와 별도로 외부 식당을 추가 추천.",
        examples=[3],
    )
    highlight_today_pick: bool = Field(
        default=True,
        description="추천 중 1곳을 '오늘의 픽' 으로 하이라이트할지 여부.",
    )


# ---------------------------------------------------------------------------
# Library (F-13, F-14, F-15)
# ---------------------------------------------------------------------------


class LibraryConfig(BaseModel):
    """도서관 좌석 알림. 잔여 좌석이 임계값 이하로 떨어지면 DM 을 발송한다."""

    reading_room_id: str = Field(
        min_length=1,
        max_length=50,
        description="대상 열람실 식별자. 도서관 시스템의 reading room id 와 일치.",
        examples=["301"],
    )
    threshold: int = Field(
        ge=0,
        description="알림 발동 잔여 좌석 임계값(개). 잔여 ≤ threshold 일 때 발송.",
        examples=[20],
    )
    urgent_threshold: int | None = Field(
        default=None,
        ge=0,
        description="긴급 알림 임계값(개). 잔여 ≤ urgent_threshold 면 강조 표시. `threshold` 이하여야 한다.",
        examples=[5],
    )

    @model_validator(mode="after")
    def _urgent_le_threshold(self) -> "LibraryConfig":
        if self.urgent_threshold is not None and self.urgent_threshold > self.threshold:
            raise ValueError("urgent_threshold must be ≤ threshold")
        return self


# ---------------------------------------------------------------------------
# Create — discriminated by NotificationType
# ---------------------------------------------------------------------------


class _TransitCreate(BaseModel):
    """교통 알림 생성 본문. `config.mode` 로 단발/정기를 다시 분기."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "TRANSIT",
                    "enabled": True,
                    "config": {
                        "mode": "arrival",
                        "station_name": "성신여대입구",
                        "line": "4호선",
                        "minutes_before": 10,
                        "include_congestion": True,
                    },
                }
            ]
        }
    )

    type: Literal[NotificationType.TRANSIT] = Field(
        description="알림 분류 discriminator. 항상 'TRANSIT'.",
    )
    enabled: bool = Field(
        default=True,
        description="생성 직후 활성화 여부. false 면 발송되지 않음.",
    )
    config: TransitConfig


class _LunchCreate(BaseModel):
    """점심 알림 생성 본문."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "LUNCH",
                    "enabled": True,
                    "config": {
                        "notify_at": "11:00:00",
                        "max_price": 12000,
                        "recommend_count": 3,
                        "highlight_today_pick": True,
                    },
                }
            ]
        }
    )

    type: Literal[NotificationType.LUNCH] = Field(
        description="알림 분류 discriminator. 항상 'LUNCH'.",
    )
    enabled: bool = Field(
        default=True,
        description="생성 직후 활성화 여부.",
    )
    config: LunchConfig


class _LibraryCreate(BaseModel):
    """도서관 알림 생성 본문."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "LIBRARY",
                    "enabled": True,
                    "config": {
                        "reading_room_id": "301",
                        "threshold": 20,
                        "urgent_threshold": 5,
                    },
                }
            ]
        }
    )

    type: Literal[NotificationType.LIBRARY] = Field(
        description="알림 분류 discriminator. 항상 'LIBRARY'.",
    )
    enabled: bool = Field(
        default=True,
        description="생성 직후 활성화 여부.",
    )
    config: LibraryConfig


NotificationCreate = Annotated[
    Union[_TransitCreate, _LunchCreate, _LibraryCreate],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Update — type별 분리. config는 전체 교체.
# ---------------------------------------------------------------------------


class TransitUpdate(BaseModel):
    """교통 알림 부분 수정. `config` 를 함께 보내면 **전체 교체** 된다 (부분 merge X)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "enabled": False,
                },
                {
                    "config": {
                        "mode": "recurring",
                        "station_name": "성신여대입구",
                        "line": "4호선",
                        "start_time": "08:00:00",
                        "end_time": "10:00:00",
                        "repeat_interval_minutes": 5,
                        "include_congestion": True,
                    }
                },
            ]
        }
    )

    enabled: bool | None = Field(
        default=None,
        description="활성화 토글. null 이면 변경하지 않음.",
    )
    config: TransitConfig | None = Field(
        default=None,
        description="새 config. null 이 아니면 기존 config 를 통째로 대체.",
    )


class LunchUpdate(BaseModel):
    """점심 알림 부분 수정. `config` 는 전체 교체."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"enabled": False},
                {
                    "config": {
                        "notify_at": "11:30:00",
                        "max_price": 15000,
                        "recommend_count": 5,
                        "highlight_today_pick": False,
                    }
                },
            ]
        }
    )

    enabled: bool | None = Field(
        default=None,
        description="활성화 토글.",
    )
    config: LunchConfig | None = Field(
        default=None,
        description="새 config. 기존 config 를 통째로 대체.",
    )


class LibraryUpdate(BaseModel):
    """도서관 알림 부분 수정. `config` 는 전체 교체."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"enabled": True},
                {
                    "config": {
                        "reading_room_id": "301",
                        "threshold": 30,
                        "urgent_threshold": 10,
                    }
                },
            ]
        }
    )

    enabled: bool | None = Field(
        default=None,
        description="활성화 토글.",
    )
    config: LibraryConfig | None = Field(
        default=None,
        description="새 config. 기존 config 를 통째로 대체.",
    )


# ---------------------------------------------------------------------------
# Read — Swagger에서 type별 정확한 config가 보이도록 discriminated union.
# ---------------------------------------------------------------------------


class _TransitRead(BaseModel):
    """교통 알림 응답 본문."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 11,
                    "user_id": 42,
                    "type": "TRANSIT",
                    "enabled": True,
                    "config": {
                        "mode": "arrival",
                        "station_name": "성신여대입구",
                        "line": "4호선",
                        "minutes_before": 10,
                        "include_congestion": True,
                    },
                    "created_at": "2026-05-20T03:21:09+00:00",
                    "updated_at": "2026-05-20T03:21:09+00:00",
                }
            ]
        },
    )

    id: int = Field(description="알림 설정 PK.", examples=[11])
    user_id: int = Field(description="소유자 user.id.", examples=[42])
    type: Literal[NotificationType.TRANSIT] = Field(
        description="알림 분류. 항상 'TRANSIT'.",
    )
    enabled: bool = Field(description="활성화 여부.")
    config: TransitConfig
    created_at: datetime = Field(description="최초 생성 시각 (ISO 8601, UTC).")
    updated_at: datetime = Field(description="마지막 갱신 시각.")


class _LunchRead(BaseModel):
    """점심 알림 응답 본문."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 12,
                    "user_id": 42,
                    "type": "LUNCH",
                    "enabled": True,
                    "config": {
                        "notify_at": "11:00:00",
                        "max_price": 12000,
                        "recommend_count": 3,
                        "highlight_today_pick": True,
                    },
                    "created_at": "2026-05-20T03:22:00+00:00",
                    "updated_at": "2026-05-20T03:22:00+00:00",
                }
            ]
        },
    )

    id: int = Field(description="알림 설정 PK.", examples=[12])
    user_id: int = Field(description="소유자 user.id.", examples=[42])
    type: Literal[NotificationType.LUNCH] = Field(
        description="알림 분류. 항상 'LUNCH'.",
    )
    enabled: bool = Field(description="활성화 여부.")
    config: LunchConfig
    created_at: datetime = Field(description="최초 생성 시각.")
    updated_at: datetime = Field(description="마지막 갱신 시각.")


class _LibraryRead(BaseModel):
    """도서관 알림 응답 본문."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 13,
                    "user_id": 42,
                    "type": "LIBRARY",
                    "enabled": True,
                    "config": {
                        "reading_room_id": "301",
                        "threshold": 20,
                        "urgent_threshold": 5,
                    },
                    "created_at": "2026-05-20T03:23:00+00:00",
                    "updated_at": "2026-05-20T03:23:00+00:00",
                }
            ]
        },
    )

    id: int = Field(description="알림 설정 PK.", examples=[13])
    user_id: int = Field(description="소유자 user.id.", examples=[42])
    type: Literal[NotificationType.LIBRARY] = Field(
        description="알림 분류. 항상 'LIBRARY'.",
    )
    enabled: bool = Field(description="활성화 여부.")
    config: LibraryConfig
    created_at: datetime = Field(description="최초 생성 시각.")
    updated_at: datetime = Field(description="마지막 갱신 시각.")


NotificationRead = Annotated[
    Union[_TransitRead, _LunchRead, _LibraryRead],
    Field(discriminator="type"),
]


_READ_MODEL_BY_TYPE: dict[NotificationType, type[BaseModel]] = {
    NotificationType.TRANSIT: _TransitRead,
    NotificationType.LUNCH: _LunchRead,
    NotificationType.LIBRARY: _LibraryRead,
}


def read_from_orm(orm_obj: Any) -> BaseModel:
    """ORM Notification → type별 Read 모델. JSONB config의 내부 discriminator는
    각 Config의 Pydantic 검증이 자동으로 처리한다."""
    model = _READ_MODEL_BY_TYPE[orm_obj.type]
    return model.model_validate(orm_obj)
