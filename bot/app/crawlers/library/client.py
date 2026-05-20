"""건국대 도서관 열람실 좌석 조회 클라이언트.

example-response.json 형태(`data.list[].seats.{total,available}`, `.name`,
`.roomType.name`)를 반환하는 좌석 API 를 호출해 **논리 열람실 번호**별로 집계한다.
크롤러 응답의 물리 id 가 아니라 name('제 N열람실 (A)')을 파싱해 번호로 그룹 합산하므로
제1·제3열람실의 A/B 분리는 자연스럽게 합쳐지고, 번호 0 은 전체 열람실 합산을 뜻한다.

Redis TTL 캐시는 §C-1 이후. 현재는 모듈 dict TTL 캐시로 한 틱당 외부호출을 1회로 합친다.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

import httpx
import structlog

from app.core.config import Settings
from app.crawlers.library.exceptions import LibraryCrawlerFailed

_logger = structlog.get_logger(__name__)

# roomType.name 이 '열람실' 인 행만 대상(스터디룸·노트북실 등 제외).
_READING_ROOM_TYPE = "열람실"
# '제 1열람실 (A)' → 1. 공백 유무·괄호 표기에 무관하게 번호만 추출.
_ROOM_NAME_RE = re.compile(r"제\s*(\d+)\s*열람실")
# 전체 열람실 합산을 가리키는 논리 번호.
_ALL_ROOMS_NUMBER = 0
# 모듈 캐시 TTL(초). 5초 폴링 + F-13 30초 SLA 사이에서 외부호출 빈도를 낮춘다.
_CACHE_TTL_SECONDS = 5.0


@dataclass(frozen=True)
class RoomSeats:
    """논리 열람실 한 곳의 좌석 집계. room_number 0 = 전체 열람실 합산."""

    room_number: int
    label: str
    total: int
    available: int


# 모듈 TTL 캐시: url → (monotonic_deadline, snapshot).
# 다수 구독·짧은 폴링이 한 번의 외부호출로 합쳐진다.
_cache: dict[str, tuple[float, dict[int, RoomSeats]]] = {}
_cache_lock = asyncio.Lock()


class LibraryClient:
    """도서관 좌석 API 래퍼.

    http_client 는 lifespan 의 공유 AsyncClient 를 주입받는다. 인스턴스 내부에서
    새 클라이언트를 만들지 않는다. library_seat_url 미설정 시 즉시 실패한다
    (SubwayClient 의 키 검증과 동형).
    """

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        url = settings.library_seat_url
        if not url:
            raise LibraryCrawlerFailed("library_url_missing")
        self._url: str = url
        self._http = http_client

    async def fetch_seats(self) -> dict[int, RoomSeats]:
        """열람실 좌석을 논리 번호별로 집계해 반환한다. 키 0 = 전체 합산.

        모듈 TTL 캐시가 유효하면 외부호출을 생략한다.
        """
        async with _cache_lock:
            now = time.monotonic()
            cached = _cache.get(self._url)
            if cached is not None and cached[0] > now:
                _logger.debug("library_cache_hit", rooms=len(cached[1]))
                return cached[1]

            snapshot = await self._fetch_and_parse()
            _cache[self._url] = (now + _CACHE_TTL_SECONDS, snapshot)
            _logger.info("library_fetched", rooms=len(snapshot))
            return snapshot

    async def _fetch_and_parse(self) -> dict[int, RoomSeats]:
        try:
            response = await self._http.get(self._url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            _logger.warning(
                "library_api_http_error", status_code=exc.response.status_code
            )
            raise LibraryCrawlerFailed(
                f"library_http_{exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            _logger.warning("library_api_request_failed", error=str(exc)[:200])
            raise LibraryCrawlerFailed("library_request_failed") from exc
        except Exception as exc:  # noqa: BLE001
            _logger.warning("library_api_parse_failed", error=str(exc)[:200])
            raise LibraryCrawlerFailed("library_parse_failed") from exc

        return self._aggregate(data)

    @staticmethod
    def _aggregate(data: object) -> dict[int, RoomSeats]:
        if not isinstance(data, dict):
            raise LibraryCrawlerFailed("library_unexpected_format")
        payload = data.get("data")
        if not isinstance(payload, dict):
            raise LibraryCrawlerFailed("library_no_data_block")
        rows = payload.get("list")
        if not isinstance(rows, list):
            raise LibraryCrawlerFailed("library_no_list")

        totals: dict[int, int] = {}
        avails: dict[int, int] = {}
        for row in rows:
            parsed = _parse_row(row)
            if parsed is None:
                continue
            number, total, available = parsed
            totals[number] = totals.get(number, 0) + total
            avails[number] = avails.get(number, 0) + available

        snapshot: dict[int, RoomSeats] = {}
        all_total = 0
        all_available = 0
        for number in sorted(totals):
            total = totals[number]
            available = avails[number]
            snapshot[number] = RoomSeats(
                room_number=number,
                label=f"제{number}열람실",
                total=total,
                available=available,
            )
            all_total += total
            all_available += available

        if snapshot:
            snapshot[_ALL_ROOMS_NUMBER] = RoomSeats(
                room_number=_ALL_ROOMS_NUMBER,
                label="전체 열람실",
                total=all_total,
                available=all_available,
            )
        return snapshot


def _parse_row(row: object) -> tuple[int, int, int] | None:
    """좌석 API 행 → (room_number, total, available). 대상 외 행이면 None."""
    if not isinstance(row, dict):
        return None
    room_type = row.get("roomType")
    if not isinstance(room_type, dict) or room_type.get("name") != _READING_ROOM_TYPE:
        return None
    match = _ROOM_NAME_RE.search(str(row.get("name", "")))
    if match is None:
        return None
    seats = row.get("seats")
    if not isinstance(seats, dict):
        return None
    try:
        total = int(seats.get("total", 0))
        available = int(seats.get("available", 0))
    except (TypeError, ValueError):
        return None
    return int(match.group(1)), total, available


def _clear_cache_for_tests() -> None:
    _cache.clear()
