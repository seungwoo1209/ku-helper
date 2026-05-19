"""즉시 발송 lunch DM 임베드 빌더."""

import discord

from app.crawlers.lunch.client import LunchMenu
from app.crawlers.restaurants.client import Restaurant

_COLOR = 0xF5A623
_MAX_FIELD_LENGTH = 1024
_MAX_CORNER_FIELDS = 6


def build_lunch_immediate_embed(
    menu: LunchMenu, restaurants: tuple[Restaurant, ...]
) -> discord.Embed:
    """학식 코너 + 추천 맛집 3건을 한 임베드에 담는다."""
    embed = discord.Embed(
        title=f"오늘의 학식 — {menu.cafeteria_name}",
        description=f"{menu.weekday}요일 · {menu.date_str}",
        color=_COLOR,
    )

    if not menu.corners:
        embed.add_field(
            name="학식",
            value="오늘은 학식 운영 정보가 없습니다.",
            inline=False,
        )
    else:
        for corner in menu.corners[:_MAX_CORNER_FIELDS]:
            menus_text = (
                "\n".join(corner.menus[:3]) if corner.menus else "메뉴 정보 없음"
            )
            value = f"{corner.time} · {corner.meal}\n{menus_text}"
            embed.add_field(
                name=corner.name,
                value=value[:_MAX_FIELD_LENGTH],
                inline=True,
            )

    if restaurants:
        lines = [
            f"{i + 1}. {r.name} · {r.category}"
            + (f" · {r.address}" if r.address else "")
            for i, r in enumerate(restaurants)
        ]
        embed.add_field(
            name="추천 맛집",
            value="\n".join(lines)[:_MAX_FIELD_LENGTH],
            inline=False,
        )

    embed.set_footer(text="네이버 지역 검색 · 무작위 3곳")
    return embed
