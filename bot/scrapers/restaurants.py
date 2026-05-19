"""
네이버 지역 검색 API를 이용한 건국대 주변 맛집 수집기

캐시 전략:
  - bot/data/restaurants_cache.json 에 하루 단위로 저장
  - 같은 날짜라면 캐시에서 반환 (API 호출 없음)
  - 날짜가 바뀌면 다시 수집 후 저장

Naver Local Search API:
  - 엔드포인트: https://openapi.naver.com/v1/search/local.json
  - 헤더: X-Naver-Client-Id / X-Naver-Client-Secret
  - 카테고리별 쿼리 10개 × 5건 → 중복 제거 후 최대 ~50곳
  - 환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
"""

import re
import json
import random
from datetime import date
from html import unescape
from os import getenv
from pathlib import Path
from urllib.parse import quote

import httpx

NAVER_LOCAL_URL = "https://openapi.naver.com/v1/search/local.json"
_PAGE_SIZE  = 5
_CACHE_PATH = Path(__file__).parent.parent / "data" / "restaurants_cache.json"

# 단일 "건대 맛집" 쿼리는 5~7곳만 반환 → 카테고리별로 분산해 풀 확보
_QUERIES = [
    "건대 한식", "건대 일식", "건대 중식", "건대 양식", "건대 분식",
    "건대 고기", "건대 라멘", "건대 초밥", "건대 돈까스", "건대 해산물",
]


# ── 캐시 헬퍼 ────────────────────────────────────────────────

def _today_key() -> str:
    return date.today().isoformat()


def _load_cache() -> dict | None:
    if not _CACHE_PATH.exists():
        return None
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(data: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 공개 API ─────────────────────────────────────────────────

async def fetch_restaurant_pool() -> list[dict]:
    """오늘 날짜의 캐시가 있으면 반환, 없으면 Naver API로 새로 가져온다."""
    cache = _load_cache()
    if cache and cache.get("date") == _today_key():
        return cache.get("pool", [])

    pool = await _fetch_from_naver()
    _save_cache({"date": _today_key(), "pool": pool})
    return pool


def pick_restaurants(pool: list[dict], k: int = 3) -> list[dict]:
    """풀에서 k곳을 무작위로 골라 반환한다."""
    return random.sample(pool, k=min(k, len(pool))) if pool else []


def clear_cache() -> None:
    if _CACHE_PATH.exists():
        _CACHE_PATH.unlink()


# ── Naver API 호출 ────────────────────────────────────────────

async def _fetch_from_naver() -> list[dict]:
    client_id     = getenv("NAVER_CLIENT_ID", "")
    client_secret = getenv("NAVER_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise EnvironmentError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 설정되지 않았습니다."
        )

    headers = {
        "X-Naver-Client-Id":     client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    seen: set[str] = set()
    results: list[dict] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for query in _QUERIES:
            resp = await client.get(
                NAVER_LOCAL_URL,
                headers=headers,
                params={"query": query, "display": _PAGE_SIZE, "start": 1, "sort": "random"},
            )
            resp.raise_for_status()

            for item in resp.json().get("items", []):
                normalized = _normalize(item)
                dedup_key = f"{normalized['name']}|{normalized['address']}"
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    results.append(normalized)

    return results


# ── 정규화 ───────────────────────────────────────────────────

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return unescape(_HTML_TAG_RE.sub("", text)).strip()


def _shorten_address(addr: str) -> str:
    return re.sub(r"^(서울특별시|서울시|서울)\s*", "", addr).strip()


def _shorten_category(cat: str) -> str:
    return cat.split(">")[-1].strip() if cat else ""


def _normalize(item: dict) -> dict:
    name = _clean(item.get("title", ""))
    return {
        "name":     name,
        "category": _shorten_category(item.get("category", "")),
        "address":  _shorten_address(item.get("roadAddress") or item.get("address", "")),
        "link":     f"https://map.naver.com/p/search/{quote(name)}",
    }
