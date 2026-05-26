"""서울시 지하철 실시간 도착정보 API 클라이언트.

docs/seoul_subway_realtime_arrival_api.md 명세 기반.
Redis TTL 캐시: 키 `subway:arrivals:{station_name}`, TTL 30초.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
import structlog

from app.core.config import Settings
from app.crawlers.subway.exceptions import SubwayApiAuthFailed, SubwayApiUnavailable

if TYPE_CHECKING:
    from redis.asyncio import Redis

_logger = structlog.get_logger(__name__)

# docs/seoul_subway_realtime_arrival_api.md §4.1 호선 코드표.
_SUBWAY_ID_TO_LINE: dict[str, str] = {
    "1001": "1호선",
    "1002": "2호선",
    "1003": "3호선",
    "1004": "4호선",
    "1005": "5호선",
    "1006": "6호선",
    "1007": "7호선",
    "1008": "8호선",
    "1009": "9호선",
    "1065": "공항철도",
    "1067": "경춘선",
    "1075": "수인분당선",
    "1077": "신분당선",
    "1092": "우이신설선",
    "1093": "서해선",
    "1081": "경강선",
    "1032": "GTX-A",
    "1061": "중앙선",
    "1063": "경의중앙선",
}

_BASE_URL = "http://swopenAPI.seoul.go.kr/api/subway"
_END_INDEX = 30
_HTTP_TIMEOUT_SECONDS = 10.0

# URL 로그 출력 시 API key 자리를 대체하는 자리표시자.
_KEY_PLACEHOLDER = "<API_KEY>"

# recptnDt 파싱을 시도할 포맷 목록. 먼저 일치하는 항목이 사용된다.
_RECPTN_DT_FORMATS: list[str] = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
]

_KST = ZoneInfo("Asia/Seoul")

# Redis TTL (초).
_REDIS_TTL_SECONDS = 30


@dataclass(frozen=True)
class SubwayArrival:
    """정규화된 지하철 실시간 도착 정보 한 건."""

    station_name: str
    subway_id: str
    line_label: str
    direction: str
    headed_for: str
    arrival_message: str
    arrival_message_detail: str
    arrival_seconds: int
    train_no: str
    arvl_code: int
    train_type: str
    # trainLineNm: 도착지 방면 전체 문자열 (예: "성수행(목적지역) - 구로디지털단지방면(다음역)")
    train_line_name: str
    # recptnDt: KST naive → aware → UTC aware 변환. 파싱 실패 시 None.
    received_at: datetime | None


class SubwayClient:
    """서울시 실시간 지하철 도착정보 API 래퍼.

    http_client 는 lifespan 에서 1회 생성한 공유 AsyncClient 를 주입받는다.
    redis 는 TTL 캐시용. 한 틱 내 같은 station 중복 Redis 조회를 막기 위해
    호출자(worker)가 arrivals_cache dict 를 L1 캐시로 유지한다.
    """

    def __init__(
        self, http_client: httpx.AsyncClient, settings: Settings, redis: "Redis"
    ) -> None:
        # subway_api_key 가 None 이거나 빈값이면 즉시 실패.
        raw_key = (
            settings.subway_api_key.get_secret_value()
            if settings.subway_api_key is not None
            else None
        )
        if not raw_key:
            raise SubwayApiAuthFailed()
        # SecretStr 값은 여기서 1회만 풀어 인스턴스 변수에 저장. 이후 외부 노출 금지.
        self._api_key: str = raw_key
        self._http_client = http_client
        self._redis = redis

    async def fetch_arrivals(self, station_name: str) -> list[SubwayArrival]:
        """역명으로 실시간 도착 정보를 조회한다.

        Redis TTL 캐시(30s) hit 시 외부 API 호출을 생략한다.
        반환값은 SubwayArrival 리스트. 해당 역 데이터 없음(INFO-200) → 빈 리스트.
        """
        redis_key = f"subway:arrivals:{station_name}"
        raw = await cast("Awaitable[str | None]", self._redis.get(redis_key))
        if raw is not None:
            _logger.debug("subway_cache_hit", station_name=station_name)
            return _deserialize_arrivals(raw)

        arrivals = await self._fetch_from_api(station_name)
        serialized = json.dumps(
            [asdict(a) for a in arrivals],
            default=str,
            ensure_ascii=False,
        )
        await cast(
            "Awaitable[object]",
            self._redis.setex(redis_key, _REDIS_TTL_SECONDS, serialized),
        )
        return arrivals

    async def _fetch_from_api(self, station_name: str) -> list[SubwayArrival]:
        encoded = quote(station_name, safe="")
        url = f"{_BASE_URL}/{self._api_key}/json/realtimeStationArrival/0/{_END_INDEX}/{encoded}"
        # 로그에는 key 를 자리표시자로 마스킹한 URL 만 사용한다.
        masked_url = f"{_BASE_URL}/{_KEY_PLACEHOLDER}/json/realtimeStationArrival/0/{_END_INDEX}/{encoded}"

        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            _logger.warning(
                "subway_api_http_error",
                status_code=exc.response.status_code,
                masked_url=masked_url,
            )
            raise SubwayApiUnavailable() from exc
        except httpx.HTTPError as exc:
            _logger.warning(
                "subway_api_request_failed",
                error=str(exc)[:200],
                masked_url=masked_url,
            )
            raise SubwayApiUnavailable() from exc
        except Exception as exc:
            _logger.warning(
                "subway_api_parse_failed",
                error=str(exc)[:200],
                masked_url=masked_url,
            )
            raise SubwayApiUnavailable() from exc

        return self._parse_response(data, masked_url)

    def _parse_response(self, data: object, masked_url: str) -> list[SubwayArrival]:
        if not isinstance(data, dict):
            _logger.warning("subway_api_unexpected_format", masked_url=masked_url)
            raise SubwayApiUnavailable()

        # 서울 API 응답은 두 가지 형태다.
        # 성공(INFO-000): {"errorMessage": {"code": "INFO-000", ...}, "realtimeArrivalList": [...]}
        # 오류(INFO-200 등): {"status": 500, "code": "INFO-200", "message": "...", "total": 0}
        # 중첩 형태에 code 가 있으면 그것을 우선 사용하고, 없으면 top-level code 를 사용한다.
        error_block = data.get("errorMessage")
        nested_code = error_block.get("code") if isinstance(error_block, dict) else None
        code: str = nested_code or str(data.get("code", ""))

        if code == "INFO-000":
            rows = data.get("realtimeArrivalList", [])
            if not isinstance(rows, list):
                return []
            return [self._row_to_arrival(row) for row in rows if isinstance(row, dict)]

        if code == "INFO-200":
            return []

        if code == "INFO-100":
            _logger.warning("subway_api_auth_failed", masked_url=masked_url)
            raise SubwayApiAuthFailed()

        _logger.warning("subway_api_error_code", code=code, masked_url=masked_url)
        raise SubwayApiUnavailable()

    @staticmethod
    def _row_to_arrival(row: dict[str, object]) -> SubwayArrival:
        subway_id = str(row.get("subwayId", ""))
        line_label = _SUBWAY_ID_TO_LINE.get(subway_id, "알 수 없음")

        try:
            arrival_seconds = int(str(row.get("barvlDt", "0")))
        except (ValueError, TypeError):
            arrival_seconds = 0

        return SubwayArrival(
            station_name=str(row.get("statnNm", "")),
            subway_id=subway_id,
            line_label=line_label,
            direction=str(row.get("updnLine", "")),
            headed_for=str(row.get("bstatnNm", "")),
            arrival_message=str(row.get("arvlMsg2", "")),
            arrival_message_detail=str(row.get("arvlMsg3", "")),
            arrival_seconds=arrival_seconds,
            train_no=str(row.get("btrainNo", "")),
            arvl_code=int(str(row.get("arvlCd", "99"))),
            train_type=str(row.get("btrainSttus", "")),
            train_line_name=str(row.get("trainLineNm", "")),
            received_at=_parse_recptn_dt(str(row.get("recptnDt", ""))),
        )


def _deserialize_arrivals(raw: str) -> list[SubwayArrival]:
    """Redis 캐시 JSON → SubwayArrival 리스트. 모듈 내부 전용."""
    items: list[dict[str, object]] = json.loads(raw)
    result: list[SubwayArrival] = []
    for item in items:
        received_at_raw = item.get("received_at")
        received_at: datetime | None = None
        if isinstance(received_at_raw, str) and received_at_raw:
            try:
                received_at = datetime.fromisoformat(received_at_raw)
            except ValueError:
                received_at = None
        result.append(
            SubwayArrival(
                station_name=str(item.get("station_name", "")),
                subway_id=str(item.get("subway_id", "")),
                line_label=str(item.get("line_label", "")),
                direction=str(item.get("direction", "")),
                headed_for=str(item.get("headed_for", "")),
                arrival_message=str(item.get("arrival_message", "")),
                arrival_message_detail=str(item.get("arrival_message_detail", "")),
                arrival_seconds=int(str(item.get("arrival_seconds", 0))),
                train_no=str(item.get("train_no", "")),
                arvl_code=int(str(item.get("arvl_code", 99))),
                train_type=str(item.get("train_type", "")),
                train_line_name=str(item.get("train_line_name", "")),
                received_at=received_at,
            )
        )
    return result


def _parse_recptn_dt(raw: str) -> datetime | None:
    """KST naive 문자열 → UTC aware datetime.

    API 가 반환하는 `recptnDt` 는 KST naive 문자열이다.
    _RECPTN_DT_FORMATS 를 순서대로 시도하고, 성공한 첫 포맷을 사용한다.
    파싱에 모두 실패하거나 빈 문자열이면 None 을 반환한다.
    """
    raw = raw.strip()
    if not raw:
        return None
    for fmt in _RECPTN_DT_FORMATS:
        try:
            naive = datetime.strptime(raw, fmt)
            kst_aware = naive.replace(tzinfo=_KST)
            return kst_aware.astimezone(timezone.utc)
        except ValueError:
            continue
    _logger.warning("recptn_dt_parse_failed", raw=raw[:30])
    return None
