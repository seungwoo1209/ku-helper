from datetime import datetime, time
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.notifications.models import NotificationType


# ---------------------------------------------------------------------------
# Transit (F-06, F-07, F-08)
# ---------------------------------------------------------------------------


class _TransitArrival(BaseModel):
    """F-06 단발 도착 알림: `[start_time, end_time]` 윈도우 내 도착하는 모든 열차에 대해
    `minutes_before` 도달 시 train_no 단위로 1회씩 발송한다.

    `_TransitCreate` 의 `config` 필드로 wrap 되어 외부에 노출된다. 단독으로
    클라이언트가 다루지 않는다.
    """

    mode: Literal["arrival"] = Field(
        description="단발 모드 식별자. 'arrival' 은 윈도우 내 열차별로 도착 N 분 전 1회 발송.",
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
    direction: Literal["상행", "하행", "내선", "외선"] = Field(
        description=(
            "방향. 공공 API `updnLine` 과 동일 값. 1·3·4호선 등은 '상행'/'하행', "
            "2·5호선 등 순환선은 '내선'/'외선'."
        ),
        examples=["상행"],
    )
    start_time: time = Field(
        description="윈도우 시작 시각 (24h 'HH:MM' 또는 'HH:MM:SS'). 서버 로컬 KST.",
        examples=["08:00:00"],
    )
    end_time: time = Field(
        description="윈도우 종료 시각. `start_time` 보다 늦어야 한다 (validator).",
        examples=["10:00:00"],
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

    @model_validator(mode="after")
    def _start_before_end(self) -> "_TransitArrival":
        if self.start_time >= self.end_time:
            raise ValueError(
                "start_time must be earlier than end_time "
                "(midnight-crossing windows like 23:00 -> 01:00 are not supported; "
                "split into two notifications)"
            )
        return self


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
            raise ValueError(
                "start_time must be earlier than end_time "
                "(midnight-crossing windows like 23:00 -> 01:00 are not supported; "
                "split into two notifications)"
            )
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
    """도서관 좌석 알림 (F-13/F-14/F-15). 지정 열람실의 잔여 좌석이 임계값 이하로
    떨어지는 순간 DM 을 발송한다. 회복 후 재하락 전까지 재발송을 막는 중복 방지(F-14)와
    긴급 임계값 강조(F-15)는 발송 측에서 처리한다. 정기 현황 알림은 범위 밖이다."""

    # 건국대 상허기념도서관 열람실 번호. 제4열람실은 미운영이라 유효 집합에서 제외한다.
    # 0 은 전체 열람실 잔여석 합산(원 스펙 외 확장, docs/requirements/features.md F-13 참고).
    # 제1·제3열람실은 크롤러상 A/B 로 분리돼 있으나 잔여석은 A+B 합산으로 평가한다.
    reading_room_id: Literal[0, 1, 2, 3, 5] = Field(
        description=(
            "대상 열람실 번호. 0·1·2·3·5 중 하나. 0 은 전체 열람실 잔여석 합산을 "
            "뜻한다(원 스펙 외 확장). 1·2·3·5 는 개별 열람실(제4열람실 미운영). "
            "0(전체) 및 분리 운영되는 제1·제3열람실은 A/B 좌석을 합산해 잔여석을 계산한다."
        ),
        examples=[1],
    )
    threshold: int = Field(
        ge=0,
        description=(
            "알림 발동 잔여 좌석 임계값(개). 대상 잔여석(개별 열람실, 또는 0이면 "
            "전체 합산) ≤ threshold 로 떨어질 때 발송한다 (분리 열람실은 A/B 합산 기준)."
        ),
        examples=[20],
    )
    urgent_threshold: int | None = Field(
        default=None,
        ge=0,
        description=(
            "긴급 임계값(개). 잔여석 ≤ urgent_threshold 면 임베드를 빨간색·'긴급' "
            "표기로 강조한다(F-15). null 이면 긴급 표시를 쓰지 않으며, 값이 있으면 "
            "`threshold` 보다 엄격히 작아야 한다(같으면 긴급이 항상 일반 임계값과 "
            "동시에 발동해 강조 의미가 사라지므로 거절)."
        ),
        examples=[5],
    )

    @model_validator(mode="after")
    def _urgent_lt_threshold(self) -> "LibraryConfig":
        if (
            self.urgent_threshold is not None
            and self.urgent_threshold >= self.threshold
        ):
            raise ValueError("urgent_threshold must be strictly less than threshold")
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
                        "direction": "상행",
                        "start_time": "08:00:00",
                        "end_time": "10:00:00",
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
                        "reading_room_id": 1,
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
                        "reading_room_id": 1,
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
                        "direction": "상행",
                        "start_time": "08:00:00",
                        "end_time": "10:00:00",
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
                        "reading_room_id": 1,
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
