"""transit embeds 빌더 단위 테스트.

embed.to_dict() 로 JSON 직렬화 후 핵심 필드를 검증한다.
한국어 텍스트 변경이 있으면 이 스냅샷이 깨지는 것이 정상 (갱신 PR 처리).
"""

from datetime import datetime, timedelta, timezone

from app.crawlers.subway.client import SubwayArrival
from app.notifications.transit.embeds import (
    _ARVL_CODE_LABEL,
    _ARRIVAL_EMBED_TITLE_TEMPLATE,
    _EMPTY_DESCRIPTION,
    _EMBED_TITLE_TEMPLATE,
    _effective_seconds,
    _format_minutes_label,
    build_transit_arrival_embed,
    build_transit_recurring_embed,
)


_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


def _make_arrival(
    line_label: str = "2호선",
    direction: str = "상행",
    headed_for: str = "성수",
    arrival_seconds: int = 120,
    arvl_code: int = 1,
    train_type: str = "일반",
    train_line_name: str = "성수행(목적지역) - 구로디지털단지방면(다음역)",
    received_at: datetime | None = None,
    arrival_message: str = "도착",
    arrival_message_detail: str = "강남 도착",
) -> SubwayArrival:
    return SubwayArrival(
        station_name="강남",
        subway_id="1002",
        line_label=line_label,
        direction=direction,
        headed_for=headed_for,
        arrival_message=arrival_message,
        arrival_message_detail=arrival_message_detail,
        arrival_seconds=arrival_seconds,
        train_no="2001",
        arvl_code=arvl_code,
        train_type=train_type,
        train_line_name=train_line_name,
        received_at=received_at,
    )


# ---------------------------------------------------------------------------
# 단위: _ARVL_CODE_LABEL — §4.2 표 1:1 매핑 7개
# ---------------------------------------------------------------------------


def test_arvl_code_label_code_0() -> None:
    """arvl_code=0 → '진입'."""
    assert _ARVL_CODE_LABEL[0] == "진입"


def test_arvl_code_label_code_1() -> None:
    """arvl_code=1 → '도착'."""
    assert _ARVL_CODE_LABEL[1] == "도착"


def test_arvl_code_label_code_2() -> None:
    """arvl_code=2 → '출발'."""
    assert _ARVL_CODE_LABEL[2] == "출발"


def test_arvl_code_label_code_3() -> None:
    """arvl_code=3 → '전역 출발'."""
    assert _ARVL_CODE_LABEL[3] == "전역 출발"


def test_arvl_code_label_code_4() -> None:
    """arvl_code=4 → '전역 진입'."""
    assert _ARVL_CODE_LABEL[4] == "전역 진입"


def test_arvl_code_label_code_5() -> None:
    """arvl_code=5 → '전역 도착'."""
    assert _ARVL_CODE_LABEL[5] == "전역 도착"


def test_arvl_code_label_code_99() -> None:
    """arvl_code=99 → '운행중'."""
    assert _ARVL_CODE_LABEL[99] == "운행중"


def test_arvl_code_label_no_emoji() -> None:
    """모든 레이블에 이모지가 없다."""
    for label in _ARVL_CODE_LABEL.values():
        for ch in label:
            assert ch.isascii() or "가" <= ch <= "힣" or ch == " ", (
                f"이모지 또는 비ASCII 문자 감지: {ch!r} in {label!r}"
            )


# ---------------------------------------------------------------------------
# 테스트: arvl_code=1 → field name 에 "도착" 포함 (이모지 없음)
# ---------------------------------------------------------------------------


def test_field_name_contains_arrival_code_label_for_code_1() -> None:
    """arvl_code=1 → field name 에 '도착' 레이블 포함."""
    arr = _make_arrival(arvl_code=1, arrival_seconds=120)
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    assert "도착" in fields[0]["name"]


# ---------------------------------------------------------------------------
# 테스트: arvl_code=99 & arrival_seconds=180 & received_at=now-60s → "2분 후" (보정)
# ---------------------------------------------------------------------------


def test_field_name_shows_corrected_minutes_for_code_99() -> None:
    """arvl_code=99, arrival_seconds=180, received_at=now-60s → 유효 잔여 120초 → '2분 후'."""
    received_at = _NOW - timedelta(seconds=60)
    arr = _make_arrival(arvl_code=99, arrival_seconds=180, received_at=received_at)
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    assert "2분 후" in fields[0]["name"]


# ---------------------------------------------------------------------------
# 테스트: arvl_code=0 & effective=30 → "1분 후" ("곧 도착" 분기 제거)
# ---------------------------------------------------------------------------


def test_field_name_shows_minutes_for_short_effective_seconds() -> None:
    """arvl_code=0, arrival_seconds=30, received_at=None → effective=30 → '1분 후'."""
    arr = _make_arrival(arvl_code=0, arrival_seconds=30, received_at=None)
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    assert "1분 후" in fields[0]["name"]


# ---------------------------------------------------------------------------
# 테스트: effective_seconds <= 0 → field name 이 라벨만 (· 없음)
# ---------------------------------------------------------------------------


def test_field_name_label_only_when_effective_seconds_zero() -> None:
    """effective_seconds=0 → field name 에 '·' 없이 라벨만."""
    # received_at=now 이면 elapsed=0, arrival_seconds=0 → effective=0
    arr = _make_arrival(arvl_code=1, arrival_seconds=0, received_at=None)
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    assert fields[0]["name"] == "도착"


# ---------------------------------------------------------------------------
# 테스트: train_line_name 채워진 케이스 → field value 첫 줄 == train_line_name
# ---------------------------------------------------------------------------


def test_field_value_first_line_uses_train_line_name_when_present() -> None:
    """train_line_name 이 있으면 field value 첫 줄이 train_line_name."""
    line_name = "성수행(목적지역) - 구로디지털단지방면(다음역)"
    arr = _make_arrival(train_line_name=line_name)
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    first_line = fields[0]["value"].split("\n")[0]
    assert first_line == line_name


# ---------------------------------------------------------------------------
# 테스트: train_line_name 비었을 때 폴백 "direction → headed_for"
# ---------------------------------------------------------------------------


def test_field_value_first_line_falls_back_to_direction_headed_for() -> None:
    """train_line_name 이 빈 문자열이면 '방향 → 종착역' 폴백."""
    arr = _make_arrival(
        direction="상행",
        headed_for="성수",
        train_line_name="",
    )
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    first_line = fields[0]["value"].split("\n")[0]
    assert first_line == "상행 → 성수"


# ---------------------------------------------------------------------------
# 테스트: train_type 빈 문자열 → [train_type] 괄호 줄 없음
# ---------------------------------------------------------------------------


def test_field_value_no_train_type_bracket_when_train_type_empty() -> None:
    """train_type 이 빈 문자열이면 field value 에 '[' 괄호(열차 종류 표시)가 없다.

    recurring 빌더는 arvlMsg2/arvlMsg3 raw 줄을 항상 추가하므로
    줄 바꿈 존재 여부 대신 '[' 포함 여부로 회귀를 검증한다.
    """
    arr = _make_arrival(train_type="")
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    assert "[" not in fields[0]["value"]


# ---------------------------------------------------------------------------
# 테스트: payload arrivals[0] 에 train_line_name, received_at, effective_seconds 키 존재
# ---------------------------------------------------------------------------


def test_payload_arrival_contains_new_keys() -> None:
    """payload arrivals[0] 에 train_line_name, received_at, effective_seconds 가 있다."""
    received_at = _NOW - timedelta(seconds=30)
    arr = _make_arrival(
        arvl_code=1,
        arrival_seconds=120,
        train_line_name="성수행",
        received_at=received_at,
    )
    _, payload = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    assert len(payload["arrivals"]) == 1
    a = payload["arrivals"][0]
    assert "train_line_name" in a
    assert a["train_line_name"] == "성수행"
    assert "received_at" in a
    assert a["received_at"] == received_at.isoformat()
    assert "effective_seconds" in a
    # 120 - 30 = 90
    assert a["effective_seconds"] == 90


# ---------------------------------------------------------------------------
# 테스트: payload arrivals[0] received_at=None → None
# ---------------------------------------------------------------------------


def test_payload_arrival_received_at_none_when_no_recptn_dt() -> None:
    """received_at=None 이면 payload 의 received_at 도 None."""
    arr = _make_arrival(received_at=None)
    _, payload = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    assert payload["arrivals"][0]["received_at"] is None


# ---------------------------------------------------------------------------
# 기존 회귀 가드: 빈 arrivals → EMPTY_DESCRIPTION
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
# 기존 회귀 가드: line 불일치 → 빈 결과
# ---------------------------------------------------------------------------


def test_build_transit_recurring_embed_line_filter() -> None:
    """line 이 일치하지 않으면 EMPTY_DESCRIPTION."""
    arrivals = [_make_arrival(line_label="1호선")]

    embed, payload = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=arrivals,
        now=_NOW,
    )
    d = embed.to_dict()
    assert d.get("description") == _EMPTY_DESCRIPTION


# ---------------------------------------------------------------------------
# 기존 회귀 가드: 도착 2건 → title, fields 개수, 스냅샷
# ---------------------------------------------------------------------------


def test_build_transit_recurring_embed_with_arrivals() -> None:
    """도착 2건(상행/하행) → embed title, fields 2개."""
    arrivals = [
        _make_arrival(direction="상행", headed_for="성수", arrival_seconds=120),
        _make_arrival(
            direction="하행",
            headed_for="사당",
            arrival_seconds=300,
            train_line_name="",
        ),
    ]
    embed, payload = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=arrivals,
        now=_NOW,
    )
    d = embed.to_dict()
    assert d["title"] == _EMBED_TITLE_TEMPLATE.format(station_name="강남", line="2호선")  # type: ignore[index]
    assert len(d.get("fields", [])) == 2
    assert payload["station_name"] == "강남"
    assert len(payload["arrivals"]) == 2
    assert payload["rendered_at"] == _NOW.isoformat()


# ---------------------------------------------------------------------------
# 단위: _effective_seconds
# ---------------------------------------------------------------------------


def test_effective_seconds_no_received_at_returns_arrival_seconds() -> None:
    """received_at=None 이면 arrival_seconds 그대로."""
    arr = _make_arrival(arrival_seconds=300, received_at=None)
    assert _effective_seconds(arr, _NOW) == 300


def test_effective_seconds_with_received_at_subtracts_elapsed() -> None:
    """received_at 있으면 경과 시간 차감."""
    received_at = _NOW - timedelta(seconds=45)
    arr = _make_arrival(arrival_seconds=120, received_at=received_at)
    assert _effective_seconds(arr, _NOW) == 75


def test_effective_seconds_clamps_to_zero() -> None:
    """경과 > arrival_seconds 이면 0."""
    received_at = _NOW - timedelta(seconds=200)
    arr = _make_arrival(arrival_seconds=100, received_at=received_at)
    assert _effective_seconds(arr, _NOW) == 0


# ---------------------------------------------------------------------------
# 단위: _format_minutes_label (arvl_code 인자 없는 단순화 버전)
# ---------------------------------------------------------------------------


def test_format_minutes_label_zero_returns_empty_string() -> None:
    """effective=0 → 빈 문자열 (field name 에 라벨만)."""
    assert _format_minutes_label(0) == ""


def test_format_minutes_label_negative_returns_empty_string() -> None:
    """effective<0 → 빈 문자열."""
    assert _format_minutes_label(-1) == ""


def test_format_minutes_label_code_99_with_valid_seconds_returns_minutes() -> None:
    """effective=120 → '2분 후'."""
    assert _format_minutes_label(120) == "2분 후"


def test_format_minutes_label_30_seconds_returns_1_minute() -> None:
    """effective=30 → ceil(30/60)=1 → '1분 후' (이전 '곧 도착' 분기 없음)."""
    assert _format_minutes_label(30) == "1분 후"


def test_format_minutes_label_60_seconds_returns_1_minute() -> None:
    """effective=60 → ceil(60/60)=1 → '1분 후'."""
    assert _format_minutes_label(60) == "1분 후"


def test_format_minutes_label_61_seconds_returns_2_minutes() -> None:
    """effective=61 → ceil(61/60)=2 → '2분 후'."""
    assert _format_minutes_label(61) == "2분 후"


def test_format_minutes_label_any_positive_no_arvl_code_branch() -> None:
    """arvl_code 인자가 없으므로 코드별 분기가 없다 — 양수이면 항상 분 후."""
    assert _format_minutes_label(1) == "1분 후"
    assert _format_minutes_label(59) == "1분 후"
    assert _format_minutes_label(180) == "3분 후"


# ===========================================================================
# build_transit_arrival_embed 테스트 (F-06)
# ===========================================================================


def _make_arrival_single(
    direction: str = "상행",
    arrival_seconds: int = 120,
    arvl_code: int = 1,
    train_no: str = "A001",
    received_at: datetime | None = None,
) -> SubwayArrival:
    return SubwayArrival(
        station_name="강남",
        subway_id="1002",
        line_label="2호선",
        direction=direction,
        headed_for="성수",
        arrival_message="도착",
        arrival_message_detail="강남 도착",
        arrival_seconds=arrival_seconds,
        train_no=train_no,
        arvl_code=arvl_code,
        train_type="일반",
        train_line_name="성수행(목적지역) - 구로디지털단지방면(다음역)",
        received_at=received_at,
    )


# ---------------------------------------------------------------------------
# arrival embed 테스트 1: 제목 포맷 회귀 (분/역/방향 포함)
# ---------------------------------------------------------------------------


def test_arrival_embed_title_format() -> None:
    """build_transit_arrival_embed 제목이 역명·호선·방향을 포함한다."""
    arr = _make_arrival_single()
    embed, _ = build_transit_arrival_embed(
        station_name="강남",
        line="2호선",
        direction="상행",
        minutes_before=5,
        arrival=arr,
        now=_NOW,
    )
    d = embed.to_dict()
    expected_title = _ARRIVAL_EMBED_TITLE_TEMPLATE.format(
        station_name="강남", line="2호선", direction="상행"
    )
    assert d["title"] == expected_title


# ---------------------------------------------------------------------------
# arrival embed 테스트 2: description 에 "{minutes_before}분 전 알림"
# ---------------------------------------------------------------------------


def test_arrival_embed_description_contains_minutes_before() -> None:
    """description 이 'N분 전 알림' 형태를 포함한다."""
    arr = _make_arrival_single()
    embed, _ = build_transit_arrival_embed(
        station_name="강남",
        line="2호선",
        direction="상행",
        minutes_before=3,
        arrival=arr,
        now=_NOW,
    )
    d = embed.to_dict()
    assert d.get("description") == "3분 전 알림"


# ---------------------------------------------------------------------------
# arrival embed 테스트 3: payload 에 train_no, direction, minutes_before 키 존재
# ---------------------------------------------------------------------------


def test_arrival_embed_payload_contains_required_keys() -> None:
    """payload 에 train_no, direction, minutes_before 키가 있다."""
    arr = _make_arrival_single(train_no="T999")
    _, payload = build_transit_arrival_embed(
        station_name="강남",
        line="2호선",
        direction="상행",
        minutes_before=7,
        arrival=arr,
        now=_NOW,
    )
    assert payload["train_no"] == "T999"
    assert payload["direction"] == "상행"
    assert payload["minutes_before"] == 7


# ---------------------------------------------------------------------------
# arrival embed 테스트 4: effective_seconds ≤ 0 → field name 이 라벨만 (분 표시 없음)
# ---------------------------------------------------------------------------


def test_arrival_embed_field_name_label_only_when_effective_zero() -> None:
    """effective_seconds=0 → field name 이 '·' 없이 arvlCd 라벨만."""
    arr = _make_arrival_single(arrival_seconds=0, arvl_code=2)
    embed, _ = build_transit_arrival_embed(
        station_name="강남",
        line="2호선",
        direction="상행",
        minutes_before=5,
        arrival=arr,
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    # arvl_code=2 → "출발". 분 표시 없으므로 "·" 없어야 한다.
    assert fields[0]["name"] == "출발"
    assert "·" not in fields[0]["name"]


# ===========================================================================
# 회귀 가드: train_type "일반" 처리 (변경 1)
# ===========================================================================


def test_recurring_embed_train_type_ilban_no_bracket() -> None:
    """train_type == '일반' 이면 recurring 임베드 field value 에 '[일반]' 이 없다."""
    arr = _make_arrival(train_type="일반")
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    assert "[일반]" not in fields[0]["value"]


def test_recurring_embed_train_type_express_shows_bracket() -> None:
    """train_type == '급행' 이면 recurring 임베드 field value 에 '[급행]' 이 포함된다 (회귀 가드)."""
    arr = _make_arrival(train_type="급행")
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    assert "[급행]" in fields[0]["value"]


# ===========================================================================
# 회귀 가드: recurring 임베드에 arvlMsg2/arvlMsg3 raw 노출 (변경 2)
# ===========================================================================


def test_recurring_embed_contains_raw_messages() -> None:
    """recurring 임베드 field value 에 'arvlMsg2:' 와 'arvlMsg3:' 가 포함된다 (테스트용 raw 노출)."""
    arr = _make_arrival(
        arrival_message="[2]건대입구방면 진입",
        arrival_message_detail="건대입구 도착",
    )
    embed, _ = build_transit_recurring_embed(
        station_name="강남",
        line="2호선",
        arrivals=[arr],
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    value = fields[0]["value"]
    assert "arvlMsg2:" in value
    assert "arvlMsg3:" in value
    assert "[2]건대입구방면 진입" in value
    assert "건대입구 도착" in value


def test_arrival_embed_does_not_contain_raw_messages() -> None:
    """arrival 임베드 field value 에 'arvlMsg2:' 와 'arvlMsg3:' 가 없다 (recurring 한정 정책)."""
    arr = _make_arrival_single()
    embed, _ = build_transit_arrival_embed(
        station_name="강남",
        line="2호선",
        direction="상행",
        minutes_before=5,
        arrival=arr,
        now=_NOW,
    )
    d = embed.to_dict()
    fields = d.get("fields", [])
    assert len(fields) == 1
    value = fields[0]["value"]
    assert "arvlMsg2:" not in value
    assert "arvlMsg3:" not in value
