"""도서관 좌석 알림 임베드 빌더 (F-13/F-15).

discord.Embed 직접 인스턴스화는 이 모듈에서만 허용한다(code_style.md).
긴급(F-15)일 때 색상 빨강 + title 에 '긴급' 키워드를 포함한다.
"""

from datetime import datetime
from typing import Any

import discord

from app.crawlers.library.client import RoomSeats

_NORMAL_COLOR = discord.Color.orange()
_URGENT_COLOR = discord.Color.red()


def build_library_embed(
    room: RoomSeats,
    threshold: int,
    urgent_threshold: int | None,
    now: datetime,
) -> tuple[discord.Embed, dict[str, Any]]:
    """잔여 좌석 임계값 알림 임베드와 history payload 를 반환한다.

    urgent_threshold 가 설정되고 잔여석이 그 이하이면 긴급 표시(F-15)한다.
    """
    is_urgent = urgent_threshold is not None and room.available <= urgent_threshold

    title = (
        f"🚨 [긴급] {room.label} 잔여 좌석"
        if is_urgent
        else f"📚 {room.label} 잔여 좌석"
    )
    embed = discord.Embed(
        title=title,
        color=_URGENT_COLOR if is_urgent else _NORMAL_COLOR,
        timestamp=now,
    )
    embed.add_field(
        name="잔여 / 총 좌석",
        value=f"{room.available} / {room.total}",
        inline=True,
    )
    embed.add_field(name="알림 임계값", value=f"{threshold} 석 이하", inline=True)
    if urgent_threshold is not None:
        embed.add_field(
            name="긴급 임계값", value=f"{urgent_threshold} 석 이하", inline=True
        )

    payload: dict[str, Any] = {
        "room_number": room.room_number,
        "label": room.label,
        "available": room.available,
        "total": room.total,
        "threshold": threshold,
        "urgent_threshold": urgent_threshold,
        "is_urgent": is_urgent,
        "rendered_at": now.isoformat(),
    }
    return embed, payload
