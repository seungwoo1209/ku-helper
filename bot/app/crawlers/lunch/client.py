"""건국대 학식 주간 메뉴 크롤러 (Playwright 기반).

lifespan 에서 단일 chromium Browser 를 만들어 주입받고, 매 호출 새 BrowserContext +
Page 만 생성·종료한다. 모듈 dict 캐시는 ISO 주 단위 (asyncio.Lock 가드).

Redis TTL 캐시 도입은 §C-1 Redis 일정 이후.

페이지 구조 (2026-05 기준, `bot/scrapers/cafeteria.py` 부채 경로의 docstring 참고):
- 목록 페이지: https://www.konkuk.ac.kr/general/18211/subview.do
- "주간 메뉴" 링크 클릭 → AJAX 인라인 로딩.
- 식단 테이블 thead.evtthd / tbody.popTbd.
- col 0: 코너명, col 2: 판매시간(아침/점심), col 3~7: 월~금 메뉴(<br> 구분).
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, timedelta
from html import unescape
from typing import TYPE_CHECKING

import structlog

from app.crawlers.lunch.exceptions import LunchCrawlerFailed

if TYPE_CHECKING:
    from playwright.async_api import Browser

_logger = structlog.get_logger(__name__)

_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
_DAY_CLASSES = ["montd", "tuetd", "wedtd", "thurtd", "fritd"]
_COL_OFFSET = 3
_BR_RE = re.compile(r"<br\s*/?>", flags=re.IGNORECASE)
_CORNER_TIME_RE = re.compile(r"^(.+?)\((.+?)\)$")
_CAFETERIA_NAME = "건국대 학생식당"


@dataclass(frozen=True)
class LunchCorner:
    name: str
    time: str
    meal: str
    menus: tuple[str, ...]


@dataclass(frozen=True)
class LunchMenu:
    date_str: str
    weekday: str
    cafeteria_name: str
    corners: tuple[LunchCorner, ...]
    menus: tuple[str, ...]


_cache: dict[str, dict[str, LunchMenu]] = {}
_cache_lock = asyncio.Lock()


def _week_key(today: date) -> str:
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


class LunchClient:
    def __init__(self, browser: Browser, url: str) -> None:
        self._browser = browser
        self._url = url

    async def fetch_today_menu(self) -> LunchMenu:
        today = date.today()
        wd_idx = today.weekday()
        if wd_idx >= 5:
            return LunchMenu(
                date_str=today.isoformat(),
                weekday=_WEEKDAY_KO[wd_idx],
                cafeteria_name=_CAFETERIA_NAME,
                corners=(),
                menus=(),
            )

        week_key = _week_key(today)
        async with _cache_lock:
            cached_week = _cache.get(week_key)
            if cached_week is not None:
                cached = cached_week.get(today.isoformat())
                if cached is not None:
                    _logger.info(
                        "lunch_cache_hit",
                        iso_week=week_key,
                        date=today.isoformat(),
                    )
                    return cached

            try:
                week_corners = await self._scrape_week()
            except LunchCrawlerFailed:
                raise
            except Exception as exc:  # noqa: BLE001
                raise LunchCrawlerFailed(f"scrape_unexpected: {exc}") from exc

            monday = today - timedelta(days=wd_idx)
            days: dict[str, LunchMenu] = {}
            for i in range(5):
                day = monday + timedelta(days=i)
                corners = week_corners.get(i, ())
                lunch_only = tuple(
                    m for c in corners if c.meal == "점심" for m in c.menus
                )
                days[day.isoformat()] = LunchMenu(
                    date_str=day.isoformat(),
                    weekday=_WEEKDAY_KO[i],
                    cafeteria_name=_CAFETERIA_NAME,
                    corners=corners,
                    menus=lunch_only,
                )

            _cache[week_key] = days
            _logger.info(
                "lunch_fetched",
                iso_week=week_key,
                corner_count=sum(len(d.corners) for d in days.values()),
            )
            return days[today.isoformat()]

    async def _scrape_week(self) -> dict[int, tuple[LunchCorner, ...]]:
        # Playwright 는 호출 시점에 동적으로 import — 테스트가 _scrape_week 를 모킹할 때
        # playwright 미설치 환경에서도 import 단계가 실패하지 않게 한다.
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        try:
            context = await self._browser.new_context()
            try:
                page = await context.new_page()
                await page.goto(self._url, wait_until="networkidle", timeout=30_000)
                link = page.locator("a:has-text('주간 메뉴')").first
                await link.click()
                await page.wait_for_selector("tbody.popTbd", timeout=15_000)

                col_indices: dict[int, int] = {}
                headers = await page.locator("thead.evtthd th").all()
                for th_i, th in enumerate(headers):
                    for wd_idx, cls in enumerate(_DAY_CLASSES):
                        if wd_idx in col_indices:
                            continue
                        if await th.locator(f"span.{cls}").count() > 0:
                            col_indices[wd_idx] = th_i
                for wd_idx in range(5):
                    col_indices.setdefault(wd_idx, _COL_OFFSET + wd_idx)

                rows = await page.locator("tbody.popTbd tr").all()
                week_corners: dict[int, list[LunchCorner]] = {i: [] for i in range(5)}
                for row in rows:
                    cells = await row.locator("td").all()
                    if not cells:
                        continue
                    corner_raw = (await cells[0].inner_text()).strip()
                    meal_time = (
                        (await cells[2].inner_text()).strip() if len(cells) > 2 else ""
                    )
                    m = _CORNER_TIME_RE.match(corner_raw)
                    corner_name = m.group(1).strip() if m else corner_raw
                    sell_time = m.group(2).strip() if m else ""

                    for wd_idx, col_idx in col_indices.items():
                        if col_idx >= len(cells):
                            continue
                        menu_html = await cells[col_idx].inner_html()
                        menus = tuple(
                            unescape(item.strip())
                            for item in _BR_RE.sub("\n", menu_html).splitlines()
                            if item.strip() and item.strip() not in ("-", "—", "휴무")
                        )
                        if menus:
                            week_corners[wd_idx].append(
                                LunchCorner(
                                    name=corner_name,
                                    time=sell_time,
                                    meal=meal_time,
                                    menus=menus,
                                )
                            )
                return {i: tuple(v) for i, v in week_corners.items()}
            finally:
                await context.close()
        except PlaywrightTimeoutError as exc:
            raise LunchCrawlerFailed(f"playwright_timeout: {exc}") from exc


def _clear_cache_for_tests() -> None:
    _cache.clear()
