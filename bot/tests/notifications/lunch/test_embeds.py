"""build_lunch_immediate_embed 스냅샷 회귀 가드."""

from app.crawlers.lunch.client import LunchCorner, LunchMenu
from app.crawlers.restaurants.client import Restaurant
from app.notifications.lunch.embeds import build_lunch_immediate_embed


def test_build_lunch_immediate_embed_snapshot() -> None:
    menu = LunchMenu(
        date_str="2026-05-19",
        weekday="화",
        cafeteria_name="건국대 학생식당",
        corners=(
            LunchCorner(
                name="한식코너",
                time="11:00~13:00",
                meal="점심",
                menus=("백반", "김치찌개", "잡채"),
            ),
            LunchCorner(
                name="일식코너",
                time="11:00~13:00",
                meal="점심",
                menus=("돈까스", "우동"),
            ),
        ),
        menus=("백반", "김치찌개", "잡채", "돈까스", "우동"),
    )
    restaurants = (
        Restaurant(
            name="소담",
            category="한식",
            address="광진구 능동로 1",
            link="https://example/소담",
        ),
        Restaurant(
            name="일미",
            category="일식",
            address="광진구 화양동 2",
            link="https://example/일미",
        ),
        Restaurant(
            name="건대분식",
            category="분식",
            address="광진구 동일로 3",
            link="https://example/건대분식",
        ),
    )

    embed = build_lunch_immediate_embed(menu, restaurants)
    body = embed.to_dict()

    assert body["title"] == "오늘의 학식 — 건국대 학생식당"
    assert body["description"] == "화요일 · 2026-05-19"
    assert body["color"] == 0xF5A623
    assert body["footer"]["text"] == "네이버 지역 검색 · 무작위 3곳"
    # 코너 2건 + 추천 맛집 1건 = field 3개.
    fields = body["fields"]
    assert len(fields) == 3
    assert fields[0]["name"] == "한식코너"
    assert "백반" in fields[0]["value"]
    assert fields[2]["name"] == "추천 맛집"
    assert "1. 소담" in fields[2]["value"]
    assert "3. 건대분식" in fields[2]["value"]


def test_build_lunch_immediate_embed_handles_empty_menu_and_no_restaurants() -> None:
    menu = LunchMenu(
        date_str="2026-05-24",
        weekday="일",
        cafeteria_name="건국대 학생식당",
        corners=(),
        menus=(),
    )
    embed = build_lunch_immediate_embed(menu, ())
    body = embed.to_dict()
    # 코너가 없으면 fallback field 1건, 맛집 field 는 미생성.
    assert len(body["fields"]) == 1
    assert body["fields"][0]["name"] == "학식"
