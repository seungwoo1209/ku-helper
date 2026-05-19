"""
건국대 학생식당 주간 메뉴 크롤러 (Playwright 기반)

캐시 전략:
  - bot/data/cafeteria_cache.json 에 주(ISO week) 단위로 저장
  - 같은 주라면 JSON에서 오늘 날짜 항목을 꺼내 반환 (크롤링 없음)
  - 주가 바뀌면 전체 내용 교체 후 저장

페이지 구조 (2026-05 기준):
  - 목록 페이지: https://www.konkuk.ac.kr/general/18211/subview.do
    → "주간 메뉴" 링크 클릭 시 AJAX 인라인 로딩
  - 식단 테이블: <thead class="evtthd"> / <tbody class="popTbd">
    - col 0: 코너명 (시간 포함)
    - col 1: 구분
    - col 2: 판매시간 (아침/점심)
    - col 3~7: 월~금 메뉴 (<br> 구분)
  - 요일 헤더 span class: montd / tuetd / wedtd / thurtd / fritd
"""

import re
import json
from html import unescape
from datetime import date, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

BOARD_URL = "https://www.konkuk.ac.kr/general/18211/subview.do"

_COL_OFFSET = 3
_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
_CACHE_PATH = Path(__file__).parent.parent / "data" / "cafeteria_cache.json"


# ── 캐시 헬퍼 ────────────────────────────────────────────────


def _week_key() -> str:
    iso = date.today().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load_cache() -> dict | None:
    if not _CACHE_PATH.exists():
        return None
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(data: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def clear_cache() -> None:
    if _CACHE_PATH.exists():
        _CACHE_PATH.unlink()


# ── 공개 API ─────────────────────────────────────────────────


async def fetch_today_menu() -> dict:
    """오늘 요일에 해당하는 학식 메뉴를 반환한다. 주간 캐시가 있으면 크롤링을 건너뛴다."""
    today = date.today()
    wd_idx = today.weekday()
    wd_str = _WEEKDAY_KO[wd_idx]

    if wd_idx >= 5:
        return _make_result(today, wd_str, [], "주말은 학생식당을 운영하지 않습니다.")

    cache = _load_cache()
    if cache and cache.get("week") == _week_key():
        entry = cache.get("days", {}).get(today.isoformat())
        if entry:
            return entry

    try:
        week_corners = await _scrape_week()
    except Exception as exc:
        return _make_result(today, wd_str, [], f"크롤링 오류: {exc}")

    monday = today - timedelta(days=wd_idx)
    days: dict[str, dict] = {}
    for i in range(5):
        day = monday + timedelta(days=i)
        corners = week_corners.get(i, [])
        flat = [m for c in corners if c["meal"] == "점심" for m in c["menus"]]
        days[day.isoformat()] = _make_result(day, _WEEKDAY_KO[i], flat, None, corners)

    _save_cache({"week": _week_key(), "days": days})
    return days.get(
        today.isoformat(), _make_result(today, wd_str, [], "오늘 데이터가 없습니다.")
    )


# ── 크롤러 ───────────────────────────────────────────────────


async def _scrape_week() -> dict[int, list[dict]]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(BOARD_URL, wait_until="networkidle", timeout=30_000)
        link = page.locator("a:has-text('주간 메뉴')").first
        await link.click()
        await page.wait_for_selector("tbody.popTbd", timeout=15_000)

        day_classes = ["montd", "tuetd", "wedtd", "thurtd", "fritd"]
        col_indices: dict[int, int] = {}

        headers = await page.locator("thead.evtthd th").all()
        for th_i, th in enumerate(headers):
            for wd_idx, cls in enumerate(day_classes):
                if wd_idx in col_indices:
                    continue
                if await th.locator(f"span.{cls}").count() > 0:
                    col_indices[wd_idx] = th_i

        for wd_idx in range(5):
            col_indices.setdefault(wd_idx, _COL_OFFSET + wd_idx)

        rows = await page.locator("tbody.popTbd tr").all()
        week_corners: dict[int, list[dict]] = {i: [] for i in range(5)}

        for row in rows:
            cells = await row.locator("td").all()
            if not cells:
                continue

            corner_raw = (await cells[0].inner_text()).strip()
            meal_time = (await cells[2].inner_text()).strip() if len(cells) > 2 else ""

            m = re.match(r"^(.+?)\((.+?)\)$", corner_raw)
            corner_name = m.group(1).strip() if m else corner_raw
            sell_time = m.group(2).strip() if m else ""

            for wd_idx, col_idx in col_indices.items():
                if col_idx >= len(cells):
                    continue
                menu_html = await cells[col_idx].inner_html()
                menus = [
                    unescape(item.strip())
                    for item in re.sub(
                        r"<br\s*/?>", "\n", menu_html, flags=re.IGNORECASE
                    ).splitlines()
                    if item.strip() and item.strip() not in ("-", "—", "휴무")
                ]
                if menus:
                    week_corners[wd_idx].append(
                        {
                            "name": corner_name,
                            "time": sell_time,
                            "meal": meal_time,
                            "menus": menus,
                        }
                    )

        await browser.close()
        return week_corners


# ── 결과 빌더 ────────────────────────────────────────────────


def _make_result(
    today: date,
    wd_str: str,
    menus: list[str],
    error: str | None,
    corners: list[dict] | None = None,
) -> dict:
    return {
        "date": today.isoformat(),
        "weekday": wd_str,
        "cafeteria": "건국대 학생식당",
        "corners": corners or [],
        "menus": menus,
        "error": error,
    }
