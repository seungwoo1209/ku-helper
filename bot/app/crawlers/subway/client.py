"""서울시 지하철 실시간 도착정보 API 클라이언트.

docs/seoul_subway_realtime_arrival_api.md 명세 기반.
Redis TTL 캐시는 §C-1(Redis 도입) 이후 추가한다.
"""

from dataclasses import dataclass
from urllib.parse import quote

import httpx
import structlog

from app.core.config import Settings
from app.crawlers.subway.exceptions import SubwayApiAuthFailed, SubwayApiUnavailable

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


class SubwayClient:
    """서울시 실시간 지하철 도착정보 API 래퍼.

    http_client 는 lifespan 에서 1회 생성한 공유 AsyncClient 를 주입받는다.
    SubwayClient 인스턴스 내부에서 새 클라이언트를 만들지 않는다.
    """

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
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

    async def fetch_arrivals(self, station_name: str) -> list[SubwayArrival]:
        """역명으로 실시간 도착 정보를 조회한다.

        반환값은 SubwayArrival 리스트. 해당 역 데이터 없음(INFO-200) → 빈 리스트.
        """
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

        error_block = data.get("errorMessage", {})
        if not isinstance(error_block, dict):
            _logger.warning("subway_api_no_error_block", masked_url=masked_url)
            raise SubwayApiUnavailable()

        code = error_block.get("code", "")

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
        )
