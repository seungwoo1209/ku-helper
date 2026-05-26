"""lunch 임베드 빌더 스냅샷 회귀 가드 (즉시발송 + 정기 스케줄)."""

from app.crawlers.lunch.client import LunchCorner, LunchMenu
from app.crawlers.restaurants.client import Restaurant
from app.notifications.lunch.embeds import (
    build_lunch_immediate_embed,
    build_lunch_scheduled_embed,
)


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


# ---------------------------------------------------------------------------
# build_lunch_scheduled_embed 회귀 가드
# ---------------------------------------------------------------------------


def _make_menu() -> LunchMenu:
    return LunchMenu(
        date_str="2026-05-26",
        weekday="화",
        cafeteria_name="건국대 학생식당",
        corners=(
            LunchCorner(
                name="한식코너",
                time="11:00~13:00",
                meal="점심",
                menus=("백반", "김치찌개", "잡채"),
            ),
        ),
        menus=("백반", "김치찌개", "잡채"),
    )


def _make_restaurants(n: int) -> tuple[Restaurant, ...]:
    return tuple(
        Restaurant(
            name=f"맛집{i + 1}",
            category="한식",
            address=f"광진구 {i}번지",
            link=f"https://x/{i}",
        )
        for i in range(n)
    )


def test_build_lunch_scheduled_embed_highlight_true_shows_today_pick() -> None:
    """highlight=True → '오늘의 픽' 필드가 존재해야 한다."""
    menu = _make_menu()
    restaurants = _make_restaurants(3)

    embed = build_lunch_scheduled_embed(menu, restaurants, highlight=True)
    body = embed.to_dict()

    field_names = [f["name"] for f in body["fields"]]
    assert "오늘의 픽" in field_names

    # 오늘의 픽 필드에 ⭐ 가 포함되어야 한다.
    pick_field = next(f for f in body["fields"] if f["name"] == "오늘의 픽")
    assert "⭐" in pick_field["value"]
    # 첫 번째 맛집 이름이 포함되어야 한다.
    assert "맛집1" in pick_field["value"]


def test_build_lunch_scheduled_embed_highlight_false_no_today_pick() -> None:
    """highlight=False → '오늘의 픽' 필드가 없어야 한다."""
    menu = _make_menu()
    restaurants = _make_restaurants(3)

    embed = build_lunch_scheduled_embed(menu, restaurants, highlight=False)
    body = embed.to_dict()

    field_names = [f["name"] for f in body["fields"]]
    assert "오늘의 픽" not in field_names
    # '추천 맛집' 필드는 존재해야 한다.
    assert "추천 맛집" in field_names


def test_build_lunch_scheduled_embed_renders_exact_restaurant_count() -> None:
    """받은 추천 개수만큼 렌더 — 5건 넘기면 5건, 2건 넘기면 2건."""
    menu = _make_menu()

    # 5건 넘기기.
    embed5 = build_lunch_scheduled_embed(menu, _make_restaurants(5), highlight=False)
    body5 = embed5.to_dict()
    rec_field = next(f for f in body5["fields"] if f["name"] == "추천 맛집")
    # 5개 항목이 모두 value 에 포함되어야 한다.
    for i in range(1, 6):
        assert f"맛집{i}" in rec_field["value"]

    # 2건 넘기기.
    embed2 = build_lunch_scheduled_embed(menu, _make_restaurants(2), highlight=False)
    body2 = embed2.to_dict()
    rec_field2 = next(f for f in body2["fields"] if f["name"] == "추천 맛집")
    assert "맛집1" in rec_field2["value"]
    assert "맛집2" in rec_field2["value"]
    # 3번째 항목이 없으므로 value 에 포함되지 않아야 한다.
    assert "맛집3" not in rec_field2["value"]


def test_build_lunch_scheduled_embed_snapshot_color_and_footer() -> None:
    """색상 코드·footer 텍스트 회귀 가드."""
    menu = _make_menu()
    embed = build_lunch_scheduled_embed(menu, _make_restaurants(1), highlight=True)
    body = embed.to_dict()

    assert body["color"] == 0xF5A623
    assert body["footer"]["text"] == "네이버 지역 검색"


def test_build_lunch_scheduled_embed_empty_restaurants_no_restaurant_field() -> None:
    """맛집 없으면 추천 관련 필드가 생성되지 않는다."""
    menu = _make_menu()
    embed = build_lunch_scheduled_embed(menu, (), highlight=True)
    body = embed.to_dict()

    field_names = [f["name"] for f in body["fields"]]
    assert "오늘의 픽" not in field_names
    assert "추천 맛집" not in field_names
