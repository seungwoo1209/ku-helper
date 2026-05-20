"""LibraryClient 단위 테스트.

respx 로 좌석 API 를 모킹하고 name 파싱·A/B 합산·전체(0) 합산·캐시·에러를 검증한다.
실제 응답 형태는 app/crawlers/library/example-response.json 을 그대로 사용한다.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from app.crawlers.library.client import LibraryClient, _clear_cache_for_tests
from app.crawlers.library.exceptions import LibraryCrawlerFailed

_URL = "https://library.example.test/seats"
_EXAMPLE = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "app"
        / "crawlers"
        / "library"
        / "example-response.json"
    ).read_text(encoding="utf-8")
)


def _settings(url: str | None = _URL) -> MagicMock:
    settings = MagicMock()
    settings.library_seat_url = url
    return settings


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    _clear_cache_for_tests()
    yield
    _clear_cache_for_tests()


@pytest.mark.asyncio
async def test_aggregates_split_rooms_a_b() -> None:
    """제1·제3열람실의 A/B 좌석은 available/total 이 합산되어야 한다."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(_URL).mock(return_value=httpx.Response(200, json=_EXAMPLE))
        async with httpx.AsyncClient() as http:
            snapshot = await LibraryClient(http, _settings()).fetch_seats()

    # 제1: (A)107+(B)89 available, 219+189 total
    assert snapshot[1].available == 196
    assert snapshot[1].total == 408
    # 제3: (A)97+(B)136 available, 148+192 total
    assert snapshot[3].available == 233
    assert snapshot[3].total == 340


@pytest.mark.asyncio
async def test_single_rooms() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(_URL).mock(return_value=httpx.Response(200, json=_EXAMPLE))
        async with httpx.AsyncClient() as http:
            snapshot = await LibraryClient(http, _settings()).fetch_seats()

    assert snapshot[2].available == 76
    assert snapshot[5].available == 137


@pytest.mark.asyncio
async def test_room_zero_is_all_rooms_sum() -> None:
    """번호 0 = 전체 열람실 합산."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(_URL).mock(return_value=httpx.Response(200, json=_EXAMPLE))
        async with httpx.AsyncClient() as http:
            snapshot = await LibraryClient(http, _settings()).fetch_seats()

    assert snapshot[0].available == 642
    assert snapshot[0].total == 1038
    assert snapshot[0].label == "전체 열람실"


@pytest.mark.asyncio
async def test_missing_room_number_absent() -> None:
    """응답에 없는 제4열람실은 snapshot 에 존재하지 않는다."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(_URL).mock(return_value=httpx.Response(200, json=_EXAMPLE))
        async with httpx.AsyncClient() as http:
            snapshot = await LibraryClient(http, _settings()).fetch_seats()

    assert 4 not in snapshot


@pytest.mark.asyncio
async def test_cache_hit_skips_second_call() -> None:
    """TTL 캐시 내 두 번째 호출은 외부 호출을 생략한다."""
    with respx.mock() as mock:
        route = mock.get(_URL).mock(return_value=httpx.Response(200, json=_EXAMPLE))
        async with httpx.AsyncClient() as http:
            client = LibraryClient(http, _settings())
            await client.fetch_seats()
            await client.fetch_seats()

    assert route.call_count == 1


@pytest.mark.asyncio
async def test_http_error_raises_library_crawler_failed() -> None:
    with respx.mock() as mock:
        mock.get(_URL).mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as http:
            with pytest.raises(LibraryCrawlerFailed):
                await LibraryClient(http, _settings()).fetch_seats()


@pytest.mark.asyncio
async def test_unexpected_format_raises() -> None:
    with respx.mock() as mock:
        mock.get(_URL).mock(return_value=httpx.Response(200, json={"data": {}}))
        async with httpx.AsyncClient() as http:
            with pytest.raises(LibraryCrawlerFailed):
                await LibraryClient(http, _settings()).fetch_seats()


@pytest.mark.asyncio
async def test_missing_url_raises_on_init() -> None:
    async with httpx.AsyncClient() as http:
        with pytest.raises(LibraryCrawlerFailed):
            LibraryClient(http, _settings(url=None))
