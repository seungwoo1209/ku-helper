"""RestaurantsClient 단위 테스트. Naver Local API 호출은 respx 로 모킹."""

from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.crawlers.restaurants import client as restaurants_module
from app.crawlers.restaurants.client import (
    _NAVER_LOCAL_URL,
    _QUERIES,
    RestaurantsClient,
)
from app.crawlers.restaurants.exceptions import RestaurantsCrawlerFailed


@pytest.fixture(autouse=True)
def _reset_cache() -> Any:
    restaurants_module._clear_cache_for_tests()
    yield
    restaurants_module._clear_cache_for_tests()


def _items(*names: str) -> dict[str, list[dict[str, str]]]:
    return {
        "items": [
            {
                "title": name,
                "category": "음식점>한식",
                "roadAddress": "서울특별시 광진구 능동로 1",
                "address": "서울 광진구 화양동 1",
            }
            for name in names
        ]
    }


@pytest.mark.asyncio
@respx.mock
async def test_fetch_pool_dedups_and_normalizes() -> None:
    # 모든 카테고리에 동일한 두 이름 → 응답 풀은 중복 제거되어 2건만.
    respx.get(_NAVER_LOCAL_URL).mock(
        return_value=httpx.Response(200, json=_items("소담", "일미식당"))
    )

    async with httpx.AsyncClient() as http:
        client = RestaurantsClient(http, "id", SecretStr("secret"))
        pool = await client.fetch_pool()

    assert len(pool) == 2
    names = {r.name for r in pool}
    assert names == {"소담", "일미식당"}
    soda = next(r for r in pool if r.name == "소담")
    assert soda.category == "한식"
    # "서울특별시" prefix 제거.
    assert soda.address.startswith("광진구")
    assert soda.link.startswith("https://map.naver.com/p/search/")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_pool_uses_cache_for_same_date() -> None:
    route = respx.get(_NAVER_LOCAL_URL).mock(
        return_value=httpx.Response(200, json=_items("소담"))
    )

    async with httpx.AsyncClient() as http:
        client = RestaurantsClient(http, "id", SecretStr("secret"))
        await client.fetch_pool()
        await client.fetch_pool()

    # 첫 호출만 카테고리 10건 호출. 두 번째는 캐시 hit.
    assert route.call_count == len(_QUERIES)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_pool_raises_on_http_5xx() -> None:
    respx.get(_NAVER_LOCAL_URL).mock(return_value=httpx.Response(503))

    async with httpx.AsyncClient() as http:
        client = RestaurantsClient(http, "id", SecretStr("secret"))
        with pytest.raises(RestaurantsCrawlerFailed) as exc_info:
            await client.fetch_pool()
    assert "naver_http_503" in exc_info.value.reason


@pytest.mark.asyncio
async def test_constructor_rejects_missing_credentials() -> None:
    async with httpx.AsyncClient() as http:
        with pytest.raises(RestaurantsCrawlerFailed) as exc_info:
            RestaurantsClient(http, None, SecretStr("secret"))
        assert exc_info.value.reason == "naver_credentials_missing"

        with pytest.raises(RestaurantsCrawlerFailed):
            RestaurantsClient(http, "id", None)

        with pytest.raises(RestaurantsCrawlerFailed):
            RestaurantsClient(http, "id", SecretStr(""))
