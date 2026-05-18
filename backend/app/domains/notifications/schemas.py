from datetime import datetime, time
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.notifications.models import NotificationType


# ---------------------------------------------------------------------------
# Transit (F-06, F-07, F-08)
# ---------------------------------------------------------------------------


class _TransitArrival(BaseModel):
    """F-06 단발 도착 알림: 특정 시각에 N분 전 한 번 발송."""

    mode: Literal["arrival"]
    station_name: str = Field(min_length=1, max_length=50)
    line: str = Field(min_length=1, max_length=20)
    minutes_before: int = Field(ge=1, le=120)
    include_congestion: bool = True


class _TransitRecurring(BaseModel):
    """F-07 정기 간격 알림: 시작·종료 시각 사이 N분마다 반복 발송."""

    mode: Literal["recurring"]
    station_name: str = Field(min_length=1, max_length=50)
    line: str = Field(min_length=1, max_length=20)
    start_time: time
    end_time: time
    repeat_interval_minutes: int = Field(ge=1, le=180)
    include_congestion: bool = True

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
    notify_at: time
    max_price: int | None = Field(default=None, ge=0)
    recommend_count: int = Field(default=3, ge=1, le=10)
    highlight_today_pick: bool = True


# ---------------------------------------------------------------------------
# Library (F-13, F-14, F-15)
# ---------------------------------------------------------------------------


class LibraryConfig(BaseModel):
    reading_room_id: str = Field(min_length=1, max_length=50)
    threshold: int = Field(ge=0)
    urgent_threshold: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _urgent_le_threshold(self) -> "LibraryConfig":
        if self.urgent_threshold is not None and self.urgent_threshold > self.threshold:
            raise ValueError("urgent_threshold must be ≤ threshold")
        return self


# ---------------------------------------------------------------------------
# Create — discriminated by NotificationType
# ---------------------------------------------------------------------------


class _TransitCreate(BaseModel):
    type: Literal[NotificationType.TRANSIT]
    enabled: bool = True
    config: TransitConfig


class _LunchCreate(BaseModel):
    type: Literal[NotificationType.LUNCH]
    enabled: bool = True
    config: LunchConfig


class _LibraryCreate(BaseModel):
    type: Literal[NotificationType.LIBRARY]
    enabled: bool = True
    config: LibraryConfig


NotificationCreate = Annotated[
    Union[_TransitCreate, _LunchCreate, _LibraryCreate],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Update — type별 분리. config는 전체 교체.
# ---------------------------------------------------------------------------


class TransitUpdate(BaseModel):
    enabled: bool | None = None
    config: TransitConfig | None = None


class LunchUpdate(BaseModel):
    enabled: bool | None = None
    config: LunchConfig | None = None


class LibraryUpdate(BaseModel):
    enabled: bool | None = None
    config: LibraryConfig | None = None


# ---------------------------------------------------------------------------
# Read — Swagger에서 type별 정확한 config가 보이도록 discriminated union.
# ---------------------------------------------------------------------------


class _TransitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: Literal[NotificationType.TRANSIT]
    enabled: bool
    config: TransitConfig
    created_at: datetime
    updated_at: datetime


class _LunchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: Literal[NotificationType.LUNCH]
    enabled: bool
    config: LunchConfig
    created_at: datetime
    updated_at: datetime


class _LibraryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: Literal[NotificationType.LIBRARY]
    enabled: bool
    config: LibraryConfig
    created_at: datetime
    updated_at: datetime


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
