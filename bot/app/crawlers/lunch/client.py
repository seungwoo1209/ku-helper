"""건국대 학식 주간 메뉴 크롤러 (Playwright 기반).

lifespan 에서 단일 chromium Browser 를 만들어 주입받고, 매 호출 새 BrowserContext +
Page 만 생성·종료한다. Redis TTL 캐시: 키 `lunch:menu:{iso_week}`, TTL 7일.

동시 miss 시 Playwright 중복 실행 가능성은 단일 캠퍼스 부하라 무시한다.
분산락(SET NX EX) 도입은 로드맵 부채로 남긴다.

페이지 구조 (2026-05 기준; 이전 부채 경로 `bot/scrapers/cafeteria.py` 는 삭제됨 — git 히스토리 참고):
- 목록 페이지: https://www.konkuk.ac.kr/general/18211/subview.do
- "주간 메뉴" 링크 클릭 → AJAX 인라인 로딩.
- 식단 테이블 thead.evtthd / tbody.popTbd.
- col 0: 코너명, col 2: 판매시간(아침/점심), col 3~7: 월~금 메뉴(<br> 구분).
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from html import unescape
from typing import TYPE_CHECKING, cast

import structlog

from app.crawlers.lunch.exceptions import LunchCrawlerFailed

if TYPE_CHECKING:
    from playwright.async_api import Browser
    from redis.asyncio import Redis

_logger = structlog.get_logger(__name__)

_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
_DAY_CLASSES = ["montd", "tuetd", "wedtd", "thurtd", "fritd"]
_COL_OFFSET = 3
_BR_RE = re.compile(r"<br\s*/?>", flags=re.IGNORECASE)
_CORNER_TIME_RE = re.compile(r"^(.+?)\((.+?)\)$")
_CAFETERIA_NAME = "건국대 학생식당"

# Redis TTL: 7일(초).
_REDIS_TTL_SECONDS = 7 * 24 * 3600


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


def _week_key(today: date) -> str:
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


class LunchClient:
    def __init__(self, browser: "Browser", url: str, redis: "Redis") -> None:
        self._browser = browser
        self._url = url
        self._redis = redis

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
        redis_key = f"lunch:menu:{week_key}"

        raw = await cast("Awaitable[str | None]", self._redis.get(redis_key))
        if raw is not None:
            week_data = _deserialize_week(raw)
            cached = week_data.get(today.isoformat())
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
            lunch_only = tuple(m for c in corners if c.meal == "점심" for m in c.menus)
            days[day.isoformat()] = LunchMenu(
                date_str=day.isoformat(),
                weekday=_WEEKDAY_KO[i],
                cafeteria_name=_CAFETERIA_NAME,
                corners=corners,
                menus=lunch_only,
            )

        serialized = _serialize_week(days)
        await cast(
            "Awaitable[object]",
            self._redis.setex(redis_key, _REDIS_TTL_SECONDS, serialized),
        )
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


def _serialize_week(days: dict[str, LunchMenu]) -> str:
    """LunchMenu dict → JSON 문자열. 모듈 내부 전용."""

    def _menu_to_dict(m: LunchMenu) -> dict[str, object]:
        d = asdict(m)
        # tuple → list 변환은 asdict 가 처리함. corners 내부 menus 도 list 로 변환됨.
        return d

    return json.dumps(
        {date_str: _menu_to_dict(menu) for date_str, menu in days.items()},
        ensure_ascii=False,
    )


def _deserialize_week(raw: str) -> dict[str, LunchMenu]:
    """JSON 문자열 → LunchMenu dict. 모듈 내부 전용."""
    data: dict[str, object] = json.loads(raw)
    result: dict[str, LunchMenu] = {}
    for date_str, item in data.items():
        if not isinstance(item, dict):
            continue
        corners_raw = item.get("corners", [])
        corners: tuple[LunchCorner, ...] = ()
        if isinstance(corners_raw, list):
            parsed_corners: list[LunchCorner] = []
            for c in corners_raw:
                if isinstance(c, dict):
                    menus_raw = c.get("menus", [])
                    menus = (
                        tuple(str(x) for x in menus_raw)
                        if isinstance(menus_raw, list)
                        else ()
                    )
                    parsed_corners.append(
                        LunchCorner(
                            name=str(c.get("name", "")),
                            time=str(c.get("time", "")),
                            meal=str(c.get("meal", "")),
                            menus=menus,
                        )
                    )
            corners = tuple(parsed_corners)
        menus_raw2 = item.get("menus", [])
        menus2 = (
            tuple(str(x) for x in menus_raw2) if isinstance(menus_raw2, list) else ()
        )
        result[date_str] = LunchMenu(
            date_str=str(item.get("date_str", date_str)),
            weekday=str(item.get("weekday", "")),
            cafeteria_name=str(item.get("cafeteria_name", "")),
            corners=corners,
            menus=menus2,
        )
    return result
