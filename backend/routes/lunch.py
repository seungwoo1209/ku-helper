"""
점심 API — bot/scrapers/ 를 직접 호출해 캐시를 자동 갱신한다.
- 학식: 주 단위 캐시 (주가 바뀌면 Playwright로 재수집)
- 맛집: 일 단위 캐시 (날짜가 바뀌면 Naver API로 재수집)
"""

import sys
import random
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

# backend/.env → os.environ 에 올려 scrapers의 os.getenv() 가 읽을 수 있게 함
load_dotenv(Path(__file__).parent.parent / ".env")

# ku-helper/ 루트를 sys.path에 추가해 bot.scrapers 임포트 가능하게 함
_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bot.scrapers.cafeteria import fetch_today_menu       # noqa: E402
from bot.scrapers.restaurants import fetch_restaurant_pool  # noqa: E402

router = APIRouter(prefix="/api/lunch", tags=["lunch"])


@router.get("/cafeteria")
async def get_cafeteria():
    """오늘의 학식 메뉴. 주간 캐시가 없으면 자동 크롤링."""
    data = await fetch_today_menu()
    if data.get("error"):
        raise HTTPException(status_code=503, detail=data["error"])
    return data


@router.get("/restaurants")
async def get_restaurants():
    """건국대 주변 맛집 3곳 무작위 추천. 일일 캐시가 없으면 자동 수집."""
    pool = await fetch_restaurant_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="맛집 정보를 가져올 수 없습니다.")
    return {"restaurants": random.sample(pool, k=min(3, len(pool)))}


@router.get("/today")
async def get_today():
    """학식 + 맛집 추천을 한 번에 반환한다."""
    cafeteria = await fetch_today_menu()
    pool = await fetch_restaurant_pool()
    restaurants = random.sample(pool, k=min(3, len(pool))) if pool else []
    return {"cafeteria": cafeteria, "restaurants": restaurants}
