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
_EMPTY_DESCRIPTION = "현재 도착 예정 열차가 없습니다."
_MAX_ARRIVALS_PER_DIRECTION = 2


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
    for direction, group in by_direction.items():
        sorted_group = sorted(group, key=lambda a: a.arrival_seconds)
        top = sorted_group[:_MAX_ARRIVALS_PER_DIRECTION]
        selected.extend(top)
        for arr in top:
            value = _format_arrival_value(arr)
            embed.add_field(
                name=f"{direction} → {arr.headed_for}",
                value=value,
                inline=False,
            )

    payload = _build_payload(station_name, line, selected, now)
    return embed, payload


def _format_arrival_value(arr: SubwayArrival) -> str:
    """도착 메시지 우선순위: arrival_message_detail → 분 환산."""
    if arr.arrival_message_detail:
        return arr.arrival_message_detail
    minutes = math.ceil(arr.arrival_seconds / 60)
    return f"{minutes}분 후"


def _build_payload(
    station_name: str,
    line: str,
    arrivals: list[SubwayArrival],
    now: datetime,
) -> dict[str, Any]:
    """JSON 직렬화 가능한 payload dict 반환. notification_history.payload 저장용."""
    return {
        "station_name": station_name,
        "line": line,
        "arrivals": [
            {
                "train_no": a.train_no,
                "direction": a.direction,
                "headed_for": a.headed_for,
                "arrival_seconds": a.arrival_seconds,
                "arvl_code": a.arvl_code,
                "train_type": a.train_type,
            }
            for a in arrivals
        ],
        "rendered_at": now.isoformat(),
    }
