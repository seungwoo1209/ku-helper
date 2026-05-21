"""교통 알림 임베드 빌더.

discord.Embed 직접 인스턴스화는 이 모듈에서만 허용.
Worker/Sender 는 build_* 함수만 호출한다 (code_style.md).
"""

import math
from datetime import datetime
from typing import Any

import discord

from app.crawlers.subway.client import SubwayArrival

_EMBED_TITLE_TEMPLATE = "🚇 {station_name} {line} 도착 정보"
_ARRIVAL_EMBED_TITLE_TEMPLATE = "⏰ {station_name} {line} {direction} 도착 임박"
_EMPTY_DESCRIPTION = "현재 도착 예정 열차가 없습니다."
_MAX_ARRIVALS_PER_DIRECTION = 2

# docs/seoul_subway_realtime_arrival_api.md §4.2 도착코드 → 표시 레이블.
_ARVL_CODE_LABEL: dict[int, str] = {
    0: "진입",
    1: "도착",
    2: "출발",
    3: "전역 출발",
    4: "전역 진입",
    5: "전역 도착",
    99: "운행중",
}


def build_transit_recurring_embed(
    station_name: str,
    line: str,
    arrivals: list[SubwayArrival],
    now: datetime,
) -> tuple[discord.Embed, dict[str, Any]]:
    """F-07 정기 간격 교통 알림용 임베드와 payload dict 를 반환한다.

    line 으로 1차 필터 → 방향별 그룹화 → 상위 2건 → fields 추가.
    arrivals 가 비거나 line 일치 항목이 없으면 EMPTY_DESCRIPTION 표시.
    """
    title = _EMBED_TITLE_TEMPLATE.format(station_name=station_name, line=line)
    embed = discord.Embed(
        title=title,
        color=discord.Color.blurple(),
        timestamp=now,
    )

    filtered = [a for a in arrivals if a.line_label == line]

    if not filtered:
        embed.description = _EMPTY_DESCRIPTION
        payload = _build_payload(station_name, line, [], now)
        return embed, payload

    # 방향별 그룹화 → arrival_seconds 오름차순 → 상위 2건.
    by_direction: dict[str, list[SubwayArrival]] = {}
    for arr in filtered:
        by_direction.setdefault(arr.direction, []).append(arr)

    selected: list[SubwayArrival] = []
    for _direction, group in by_direction.items():
        sorted_group = sorted(group, key=lambda a: a.arrival_seconds)
        top = sorted_group[:_MAX_ARRIVALS_PER_DIRECTION]
        selected.extend(top)
        for arr in top:
            eff = _effective_seconds(arr, now)
            label = _ARVL_CODE_LABEL.get(arr.arvl_code, "운행중")
            minutes_label = _format_minutes_label(eff)
            field_name = f"{label} · {minutes_label}" if minutes_label else label
            # 테스트용 raw 메시지 노출 (TODO: 추후 정리)
            field_value = _build_field_value(arr, include_raw_messages=True)
            embed.add_field(name=field_name, value=field_value, inline=False)

    payload = _build_payload(station_name, line, selected, now)
    return embed, payload


def build_transit_arrival_embed(
    station_name: str,
    line: str,
    direction: str,
    minutes_before: int,
    arrival: SubwayArrival,
    now: datetime,
) -> tuple[discord.Embed, dict[str, Any]]:
    """F-06 단발 도착 알림용 임베드와 payload dict 를 반환한다.

    특정 열차 1건의 도착 임박 알림. train_no 단위로 1회 발송된다.
    """
    title = _ARRIVAL_EMBED_TITLE_TEMPLATE.format(
        station_name=station_name,
        line=line,
        direction=direction,
    )
    embed = discord.Embed(
        title=title,
        color=discord.Color.blurple(),
        timestamp=now,
    )
    embed.description = f"{minutes_before}분 전 알림"

    eff = _effective_seconds(arrival, now)
    label = _ARVL_CODE_LABEL.get(arrival.arvl_code, "운행중")
    minutes_label = _format_minutes_label(eff)
    field_name = f"{label} · {minutes_label}" if minutes_label else label
    field_value = _build_field_value(arrival)
    embed.add_field(name=field_name, value=field_value, inline=False)

    payload: dict[str, Any] = {
        "station_name": station_name,
        "line": line,
        "direction": direction,
        "minutes_before": minutes_before,
        "train_no": arrival.train_no,
        "headed_for": arrival.headed_for,
        "arrival_seconds": arrival.arrival_seconds,
        "arvl_code": arrival.arvl_code,
        "train_type": arrival.train_type,
        "train_line_name": arrival.train_line_name,
        "received_at": arrival.received_at.isoformat() if arrival.received_at else None,
        "effective_seconds": eff,
        "rendered_at": now.isoformat(),
    }
    return embed, payload


def _effective_seconds(arr: SubwayArrival, now: datetime) -> int:
    """recptnDt 시차를 반영한 보정 도착 잔여 시간(초).

    received_at 이 None 이면 barvlDt(arrival_seconds) 를 그대로 반환.
    있으면 (now - received_at) 만큼 차감하되 0 미만은 0 으로 클램핑.
    """
    if arr.received_at is None:
        return arr.arrival_seconds
    elapsed = (now - arr.received_at).total_seconds()
    return max(0, int(arr.arrival_seconds - elapsed))


def _format_minutes_label(effective_seconds: int) -> str:
    """사람이 읽기 쉬운 도착 시간 레이블을 반환한다.

    - effective_seconds ≤ 0 이면 빈 문자열 (field name 에 라벨만 남김).
    - 그 외 math.ceil(seconds / 60)분 후.
    """
    if effective_seconds <= 0:
        return ""
    minutes = math.ceil(effective_seconds / 60)
    return f"{minutes}분 후"


def _build_field_value(
    arr: SubwayArrival,
    include_raw_messages: bool = False,
) -> str:
    """임베드 field value 를 구성한다.

    첫 줄: train_line_name 이 있으면 그대로, 없으면 direction → headed_for 폴백.
    둘째 줄: train_type 이 truthy 이고 "일반" 이 아닌 경우에만 [train_type] 추가.
             train_type == "일반" 이면 두 번째 줄을 추가하지 않는다.
    include_raw_messages=True 이면 arvlMsg2/arvlMsg3 원문을 마지막에 추가한다.
    테스트용 raw 메시지 노출 (TODO: 추후 정리)
    """
    first_line = (
        arr.train_line_name
        if arr.train_line_name
        else f"{arr.direction} → {arr.headed_for}"
    )
    lines = [first_line]
    if arr.train_type and arr.train_type != "일반":
        lines.append(f"[{arr.train_type}]")
    if include_raw_messages:
        lines.append(f"arvlMsg2: {arr.arrival_message}")
        lines.append(f"arvlMsg3: {arr.arrival_message_detail}")
    return "\n".join(lines)


def _build_payload(
    station_name: str,
    line: str,
    arrivals: list[SubwayArrival],
    now: datetime,
) -> dict[str, Any]:
    """JSON 직렬화 가능한 payload dict 반환. notification_history.payload 저장용."""
    arrival_dicts: list[dict[str, Any]] = []
    for a in arrivals:
        eff = _effective_seconds(a, now)
        arrival_dicts.append(
            {
                "train_no": a.train_no,
                "direction": a.direction,
                "headed_for": a.headed_for,
                "arrival_seconds": a.arrival_seconds,
                "arvl_code": a.arvl_code,
                "train_type": a.train_type,
                "train_line_name": a.train_line_name,
                "received_at": a.received_at.isoformat()
                if a.received_at is not None
                else None,
                "effective_seconds": eff,
            }
        )
    return {
        "station_name": station_name,
        "line": line,
        "arrivals": arrival_dicts,
        "rendered_at": now.isoformat(),
    }
