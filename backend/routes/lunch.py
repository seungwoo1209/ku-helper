"""
점심 API — bot/data/ 의 캐시 파일을 읽어 응답한다.
실제 크롤링/수집은 bot/scrapers/ 에서 담당한다.
"""

import json
import random
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/lunch", tags=["lunch"])

# backend/routes/ → backend/ → ku-helper/ → bot/data/
_BOT_DATA = Path(__file__).parent.parent.parent / "bot" / "data"


# ── 캐시 읽기 헬퍼 ───────────────────────────────────────────

def _read_cafeteria() -> dict | None:
    path = _BOT_DATA / "cafeteria_cache.json"
    if not path.exists():
        return None
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
        return cache.get("days", {}).get(date.today().isoformat())
    except Exception:
        return None


def _read_restaurant_pool() -> list[dict]:
    path = _BOT_DATA / "restaurants_cache.json"
    if not path.exists():
        return []
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
        if cache.get("date") == date.today().isoformat():
            return cache.get("pool", [])
        return []
    except Exception:
        return []


# ── 엔드포인트 ───────────────────────────────────────────────

@router.get("/cafeteria")
def get_cafeteria():
    """오늘의 학식 메뉴 (bot이 수집한 캐시에서 읽음)."""
    data = _read_cafeteria()
    if data is None:
        raise HTTPException(status_code=503, detail="학식 캐시가 없습니다. bot을 먼저 실행해 주세요.")
    return data


@router.get("/restaurants")
def get_restaurants():
    """건국대 주변 맛집 3곳 무작위 추천 (bot이 수집한 캐시에서 읽음)."""
    pool = _read_restaurant_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="맛집 캐시가 없습니다. bot을 먼저 실행해 주세요.")
    return {"restaurants": random.sample(pool, k=min(3, len(pool)))}


@router.get("/today")
def get_today():
    """학식 + 맛집 추천을 한 번에 반환한다."""
    cafeteria = _read_cafeteria()
    pool = _read_restaurant_pool()
    restaurants = random.sample(pool, k=min(3, len(pool))) if pool else []
    return {"cafeteria": cafeteria, "restaurants": restaurants}
