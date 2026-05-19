"""네이버 지역 검색 API 기반 건대 주변 맛집 풀 수집기.

lifespan 의 공유 httpx.AsyncClient 를 주입받고, 카테고리 10개 × 5건 호출 → dedup
→ 풀 반환. 모듈 dict 캐시(날짜 단위). Redis TTL 캐시는 §C-1 Redis 일정 이후.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date
from html import unescape
from urllib.parse import quote

import httpx
import structlog
from pydantic import SecretStr

from app.crawlers.restaurants.exceptions import RestaurantsCrawlerFailed

_logger = structlog.get_logger(__name__)

_NAVER_LOCAL_URL = "https://openapi.naver.com/v1/search/local.json"
_PAGE_SIZE = 5
_QUERIES = (
    "건대 한식",
    "건대 일식",
    "건대 중식",
    "건대 양식",
    "건대 분식",
    "건대 고기",
    "건대 라멘",
    "건대 초밥",
    "건대 돈까스",
    "건대 해산물",
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SEOUL_PREFIX_RE = re.compile(r"^(서울특별시|서울시|서울)\s*")


@dataclass(frozen=True)
class Restaurant:
    name: str
    category: str
    address: str
    link: str


_cache: dict[str, tuple[Restaurant, ...]] = {}
_cache_lock = asyncio.Lock()


class RestaurantsClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        client_id: str | None,
        client_secret: SecretStr | None,
    ) -> None:
        if not client_id or client_secret is None:
            raise RestaurantsCrawlerFailed("naver_credentials_missing")
        secret = client_secret.get_secret_value()
        if not secret:
            raise RestaurantsCrawlerFailed("naver_credentials_missing")
        self._http = http_client
        self._client_id = client_id
        self._client_secret = secret

    async def fetch_pool(self) -> tuple[Restaurant, ...]:
        key = date.today().isoformat()
        async with _cache_lock:
            cached = _cache.get(key)
            if cached is not None:
                _logger.info("restaurants_cache_hit", date=key, count=len(cached))
                return cached

            try:
                pool = await self._fetch_from_naver()
            except RestaurantsCrawlerFailed:
                raise
            except Exception as exc:  # noqa: BLE001
                raise RestaurantsCrawlerFailed(f"naver_unexpected: {exc}") from exc

            _cache[key] = pool
            _logger.info("restaurants_fetched", date=key, count=len(pool))
            return pool

    async def _fetch_from_naver(self) -> tuple[Restaurant, ...]:
        headers = {
            "X-Naver-Client-Id": self._client_id,
            "X-Naver-Client-Secret": self._client_secret,
        }
        seen: set[str] = set()
        results: list[Restaurant] = []
        for query in _QUERIES:
            try:
                response = await self._http.get(
                    _NAVER_LOCAL_URL,
                    headers=headers,
                    params={
                        "query": query,
                        "display": _PAGE_SIZE,
                        "start": 1,
                        "sort": "random",
                    },
                )
                response.raise_for_status()
                items = response.json().get("items", [])
            except httpx.HTTPStatusError as exc:
                raise RestaurantsCrawlerFailed(
                    f"naver_http_{exc.response.status_code}"
                ) from exc
            except httpx.HTTPError as exc:
                raise RestaurantsCrawlerFailed(f"naver_request_failed: {exc}") from exc

            for item in items:
                if not isinstance(item, dict):
                    continue
                normalized = _normalize(item)
                dedup_key = f"{normalized.name}|{normalized.address}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                results.append(normalized)
        return tuple(results)


def _clean(text: str) -> str:
    return unescape(_HTML_TAG_RE.sub("", text)).strip()


def _normalize(item: dict[str, object]) -> Restaurant:
    name = _clean(str(item.get("title", "")))
    category_raw = str(item.get("category", ""))
    category = category_raw.split(">")[-1].strip() if category_raw else ""
    address_raw = str(item.get("roadAddress") or item.get("address", ""))
    address = _SEOUL_PREFIX_RE.sub("", address_raw).strip()
    return Restaurant(
        name=name,
        category=category,
        address=address,
        link=f"https://map.naver.com/p/search/{quote(name)}",
    )


def _clear_cache_for_tests() -> None:
    _cache.clear()
