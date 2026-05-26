"""lunch DM 임베드 빌더.

즉시 발송(build_lunch_immediate_embed)과 정기 스케줄 발송(build_lunch_scheduled_embed)
두 종류를 제공한다. discord.Embed 직접 인스턴스화는 이 모듈에서만 허용
(code_style.md §discord.Embed 직접 인스턴스화 규칙).
"""

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


def build_lunch_scheduled_embed(
    menu: LunchMenu,
    restaurants: tuple[Restaurant, ...],
    *,
    highlight: bool = True,
) -> discord.Embed:
    """정기 스케줄 LUNCH 알림 임베드.

    restaurants 는 호출자(worker)가 recommend_count 만큼 이미 샘플한 튜플을
    그대로 받는다 — 임베드는 개수를 가정하지 않고 받은 만큼 렌더한다.

    highlight=True 이면 추천 목록의 첫 번째 항목을 "⭐ 오늘의 픽" 필드로
    별도 강조 표시한다. highlight=False 이면 균일 목록만 렌더한다.
    """
    embed = discord.Embed(
        title=f"오늘의 학식 — {menu.cafeteria_name}",
        description=f"{menu.weekday}요일 · {menu.date_str}",
        color=_COLOR,
    )

    # 학식 코너.
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

    # 추천 맛집.
    if restaurants:
        if highlight:
            # 첫 번째 항목을 "오늘의 픽"으로 강조.
            pick = restaurants[0]
            pick_value = f"⭐ {pick.name} · {pick.category}"
            if pick.address:
                pick_value += f" · {pick.address}"
            embed.add_field(
                name="오늘의 픽",
                value=pick_value[:_MAX_FIELD_LENGTH],
                inline=False,
            )
            # 나머지 항목은 균일 목록으로 렌더 (비어 있으면 필드 생략).
            rest = restaurants[1:]
            if rest:
                lines = [
                    f"{i + 2}. {r.name} · {r.category}"
                    + (f" · {r.address}" if r.address else "")
                    for i, r in enumerate(rest)
                ]
                embed.add_field(
                    name="추천 맛집",
                    value="\n".join(lines)[:_MAX_FIELD_LENGTH],
                    inline=False,
                )
        else:
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

    embed.set_footer(text="네이버 지역 검색")
    return embed
