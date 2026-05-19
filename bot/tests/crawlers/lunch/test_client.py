"""LunchClient 단위 테스트.

Playwright 의 실제 브라우저 호출은 모킹한다. `_scrape_week` 를 모킹해 dataclass
정렬·요일 매핑·캐시 동작·도메인 예외 변환만 검증.
"""

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.crawlers.lunch import client as lunch_client_module
from app.crawlers.lunch.client import LunchClient, LunchCorner
from app.crawlers.lunch.exceptions import LunchCrawlerFailed


@pytest.fixture(autouse=True)
def _reset_cache() -> Any:
    lunch_client_module._clear_cache_for_tests()
    yield
    lunch_client_module._clear_cache_for_tests()


def _make_client_with_scrape(scrape_result: Any) -> tuple[LunchClient, MagicMock]:
    browser = MagicMock()
    client = LunchClient(browser, "https://example.test")
    mock = AsyncMock(
        side_effect=scrape_result if isinstance(scrape_result, BaseException) else None
    )
    if not isinstance(scrape_result, BaseException):
        mock.return_value = scrape_result
    client._scrape_week = mock  # type: ignore[attr-defined]
    return client, mock


@pytest.mark.asyncio
async def test_fetch_today_menu_returns_dataclass_for_weekday() -> None:
    today = date.today()
    if today.weekday() >= 5:
        pytest.skip("주말 분기 별도 테스트")

    corners_by_day = {
        i: (
            LunchCorner(
                name=f"코너{i}",
                time="11:00~13:00",
                meal="점심",
                menus=(f"메뉴A{i}", f"메뉴B{i}"),
            ),
        )
        for i in range(5)
    }
    client, mock = _make_client_with_scrape(corners_by_day)

    menu = await client.fetch_today_menu()

    assert menu.cafeteria_name == "건국대 학생식당"
    assert menu.date_str == today.isoformat()
    assert len(menu.corners) == 1
    assert menu.corners[0].meal == "점심"
    # 점심 메뉴만 flatten 되어 menus 에 들어감.
    assert menu.menus == (f"메뉴A{today.weekday()}", f"메뉴B{today.weekday()}")
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_fetch_today_menu_caches_within_same_iso_week() -> None:
    today = date.today()
    if today.weekday() >= 5:
        pytest.skip("주말 분기 별도 테스트")

    corners_by_day = {i: () for i in range(5)}
    client, mock = _make_client_with_scrape(corners_by_day)

    await client.fetch_today_menu()
    await client.fetch_today_menu()

    # 두 번째 호출은 캐시 hit → scrape 1회만 실행.
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_fetch_today_menu_weekend_short_circuits() -> None:
    """주말이면 빈 corners 로 즉시 반환 (scrape 안 함)."""
    import time_machine

    # 2026-05-23 은 토요일.
    with time_machine.travel("2026-05-23", tick=False):
        client, mock = _make_client_with_scrape({i: () for i in range(5)})
        menu = await client.fetch_today_menu()

    assert menu.corners == ()
    assert menu.menus == ()
    assert mock.await_count == 0


@pytest.mark.asyncio
async def test_fetch_today_menu_converts_unexpected_exception() -> None:
    today = date.today()
    if today.weekday() >= 5:
        pytest.skip("주말 분기 별도 테스트")

    client, _ = _make_client_with_scrape(RuntimeError("page selector missing"))

    with pytest.raises(LunchCrawlerFailed) as exc_info:
        await client.fetch_today_menu()
    assert "scrape_unexpected" in exc_info.value.reason
