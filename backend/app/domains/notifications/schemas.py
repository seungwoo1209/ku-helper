from datetime import datetime, time
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.domains.notifications.models import NotificationType


class TransitConfig(BaseModel):
    station_name: str = Field(min_length=1, max_length=50)
    line: str = Field(min_length=1, max_length=20)
    minutes_before: int | None = Field(default=None, ge=1, le=120)
    repeat_interval_minutes: int | None = Field(default=None, ge=1, le=180)
    include_congestion: bool = True


class LunchConfig(BaseModel):
    notify_at: time
    max_price: int | None = Field(default=None, ge=0)
    recommend_count: int = Field(default=3, ge=1, le=10)


class LibraryConfig(BaseModel):
    reading_room_id: str = Field(min_length=1, max_length=50)
    threshold: int = Field(ge=0)
    urgent_threshold: int | None = Field(default=None, ge=0)


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


class NotificationUpdate(BaseModel):
    # type 변경은 허용하지 않는다. config는 항상 전체 교체.
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: NotificationType
    enabled: bool
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


_CONFIG_MODEL_BY_TYPE: dict[NotificationType, type[BaseModel]] = {
    NotificationType.TRANSIT: TransitConfig,
    NotificationType.LUNCH: LunchConfig,
    NotificationType.LIBRARY: LibraryConfig,
}


def validated_config_for(
    type_: NotificationType, raw: dict[str, Any]
) -> dict[str, Any]:
    """type에 맞는 config 페이로드인지 검증하고 정규화된 dict를 돌려준다."""
    model = _CONFIG_MODEL_BY_TYPE[type_]
    return model.model_validate(raw).model_dump(mode="json")
