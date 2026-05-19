"""transit embeds 빌더 단위 테스트.

embed.to_dict() 로 JSON 직렬화 후 핵심 필드를 검증한다.
한국어 텍스트 변경이 있으면 이 스냅샷이 깨지는 것이 정상 (갱신 PR 처리).
"""

import math
from datetime import datetime, timezone

from app.crawlers.subway.client import SubwayArrival
from app.notifications.transit.embeds import (
    _EMPTY_DESCRIPTION,
    _EMBED_TITLE_TEMPLATE,
    build_transit_recurring_embed,
)


_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


def _make_arrival(
    line_label: str = "2호선",
    direction: str = "상행",
    headed_for: str = "성수",
    arrival_seconds: int = 120,
    arrival_message_detail: str = "강남 도착",
) -> SubwayArrival:
    return SubwayArrival(
        station_name="강남",
        subway_id="1002",
        line_label=line_label,
        direction=direction,
        headed_for=headed_for,
        arrival_message="도착",
        arrival_message_detail=arrival_message_detail,
        arrival_seconds=arrival_seconds,
        train_no="2001",
        arvl_code=1,
        train_type="일반",
    )


# ---------------------------------------------------------------------------
# 테스트: 도착 2건 → 핵심 embed 키 검증
# ---------------------------------------------------------------------------


def test_build_transit_recurring_embed_with_arrivals() -> None:
    """도착 2건(상행/하행) → embed title, fields 개수, 첫 field name/value 검증."""
    arrivals = [
        _make_arrival(
            direction="상행",
            headed_for="성수",
            arrival_seconds=120,
            arrival_message_detail="강남 도착",
        ),
        _make_arrival(
            direction="하행",
            headed_for="사당",
            arrival_seconds=300,
            arrival_message_detail="",
        ),
    ]

    embed, payload = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=arrivals,
        now=_NOW,
    )

    d = embed.to_dict()

    # title 검증
    assert d["title"] == _EMBED_TITLE_TEMPLATE.format(station_name="강남", line="2호선")  # type: ignore

    # fields 가 2개 (상행 1건 + 하행 1건)
    assert len(d.get("fields", [])) == 2

    # 첫 번째 field: 상행
    first_field = d["fields"][0]  # type: ignore
    assert "상행" in first_field["name"]
    assert "성수" in first_field["name"]
    # arrival_message_detail 이 있으면 그것을 사용
    assert first_field["value"] == "강남 도착"

    # 두 번째 field: 하행, arrival_message_detail 없음 → 분 환산
    second_field = d["fields"][1]  # type: ignore
    assert "하행" in second_field["name"]
    expected_minutes = math.ceil(300 / 60)
    assert f"{expected_minutes}분 후" in second_field["value"]

    # payload 검증
    assert payload["station_name"] == "강남"
    assert payload["line"] == "2호선"
    assert len(payload["arrivals"]) == 2
    assert payload["rendered_at"] == _NOW.isoformat()


# ---------------------------------------------------------------------------
# 테스트: 빈 결과 → description 텍스트 확인
# ---------------------------------------------------------------------------


def test_build_transit_recurring_embed_empty_arrivals() -> None:
    """arrivals 가 비어 있으면 EMPTY_DESCRIPTION 이 표시된다."""
    embed, payload = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[],
        now=_NOW,
    )

    d = embed.to_dict()
    assert d.get("description") == _EMPTY_DESCRIPTION
    assert d.get("fields") is None or d.get("fields") == []
    assert payload["arrivals"] == []


# ---------------------------------------------------------------------------
# 테스트: line 불일치 → 빈 결과
# ---------------------------------------------------------------------------


def test_build_transit_recurring_embed_line_filter() -> None:
    """line 이 일치하지 않으면 EMPTY_DESCRIPTION."""
    arrivals = [_make_arrival(line_label="1호선")]  # 요청 line 은 2호선

    embed, payload = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=arrivals,
        now=_NOW,
    )

    d = embed.to_dict()
    assert d.get("description") == _EMPTY_DESCRIPTION
