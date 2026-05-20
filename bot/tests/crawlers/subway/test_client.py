"""SubwayClient 단위 테스트.

respx 로 서울 공공 API 를 모킹하고 응답 코드별 동작을 검증한다.
"""

from datetime import timezone
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from app.crawlers.subway.client import (
    SubwayArrival,
    SubwayClient,
    _BASE_URL,
    _END_INDEX,
    _parse_recptn_dt,
)
from app.crawlers.subway.exceptions import SubwayApiAuthFailed, SubwayApiUnavailable


# ---------------------------------------------------------------------------
# 픽스처 / 헬퍼
# ---------------------------------------------------------------------------


def _make_settings(api_key: str | None = "test-key") -> MagicMock:
    settings = MagicMock()
    if api_key is None:
        settings.subway_api_key = None
    else:
        from pydantic import SecretStr

        settings.subway_api_key = SecretStr(api_key)
    return settings


def _station_url(station: str, api_key: str = "test-key") -> str:
    from urllib.parse import quote

    encoded = quote(station, safe="")
    return f"{_BASE_URL}/{api_key}/json/realtimeStationArrival/0/{_END_INDEX}/{encoded}"


def _info_000_payload(arrivals: list[dict]) -> dict:  # type: ignore[type-arg]
    return {
        "errorMessage": {"code": "INFO-000", "message": "정상 처리되었습니다."},
        "realtimeArrivalList": arrivals,
    }


def _sample_row(
    *,
    subway_id: str = "1002",
    station_name: str = "강남",
    updn: str = "상행",
    headed_for: str = "성수",
    arv_msg2: str = "도착",
    arv_msg3: str = "강남 도착",
    barvl_dt: str = "60",
    train_no: str = "2001",
    arvl_cd: str = "1",
    train_type: str = "일반",
    train_line_nm: str = "",
    recptn_dt: str = "",
) -> dict:  # type: ignore[type-arg]
    return {
        "subwayId": subway_id,
        "statnNm": station_name,
        "updnLine": updn,
        "bstatnNm": headed_for,
        "arvlMsg2": arv_msg2,
        "arvlMsg3": arv_msg3,
        "barvlDt": barvl_dt,
        "btrainNo": train_no,
        "arvlCd": arvl_cd,
        "btrainSttus": train_type,
        "trainLineNm": train_line_nm,
        "recptnDt": recptn_dt,
    }


# ---------------------------------------------------------------------------
# 테스트: 정상 응답(INFO-000)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_arrivals_info_000_returns_subway_arrivals() -> None:
    """INFO-000 + 2건 → SubwayArrival 2개 반환. 각 필드 매핑 검증."""
    row1 = _sample_row(
        subway_id="1002",
        updn="상행",
        headed_for="성수",
        barvl_dt="120",
        train_no="2001",
    )
    row2 = _sample_row(
        subway_id="1002",
        updn="하행",
        headed_for="사당",
        barvl_dt="300",
        train_no="2002",
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get(_station_url("강남")).mock(
            return_value=httpx.Response(200, json=_info_000_payload([row1, row2]))
        )

        async with httpx.AsyncClient() as client:
            subway_client = SubwayClient(client, _make_settings())
            result = await subway_client.fetch_arrivals("강남")

    assert len(result) == 2

    arr1 = result[0]
    assert isinstance(arr1, SubwayArrival)
    assert arr1.subway_id == "1002"
    assert arr1.line_label == "2호선"
    assert arr1.direction == "상행"
    assert arr1.headed_for == "성수"
    assert arr1.arrival_seconds == 120
    assert arr1.train_no == "2001"

    arr2 = result[1]
    assert arr2.direction == "하행"
    assert arr2.headed_for == "사당"
    assert arr2.arrival_seconds == 300
    assert arr2.train_no == "2002"


# ---------------------------------------------------------------------------
# 테스트: INFO-200 (데이터 없음)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_arrivals_info_200_returns_empty_list() -> None:
    """INFO-200 → 빈 리스트 반환."""
    payload = {"errorMessage": {"code": "INFO-200", "message": "해당하는 데이터 없음"}}

    with respx.mock(assert_all_called=True) as mock:
        mock.get(_station_url("강남")).mock(
            return_value=httpx.Response(200, json=payload)
        )

        async with httpx.AsyncClient() as client:
            subway_client = SubwayClient(client, _make_settings())
            result = await subway_client.fetch_arrivals("강남")

    assert result == []


# ---------------------------------------------------------------------------
# 테스트: INFO-100 (인증 실패)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_arrivals_info_100_raises_auth_failed() -> None:
    """INFO-100 → SubwayApiAuthFailed raise."""
    payload = {"errorMessage": {"code": "INFO-100", "message": "인증키 유효하지 않음"}}

    with respx.mock(assert_all_called=True) as mock:
        mock.get(_station_url("강남")).mock(
            return_value=httpx.Response(200, json=payload)
        )

        async with httpx.AsyncClient() as client:
            subway_client = SubwayClient(client, _make_settings())
            with pytest.raises(SubwayApiAuthFailed):
                await subway_client.fetch_arrivals("강남")


# ---------------------------------------------------------------------------
# 테스트: ERROR-500 (서버 오류)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_arrivals_error_500_raises_unavailable() -> None:
    """errorMessage.code = ERROR-500 → SubwayApiUnavailable."""
    payload = {"errorMessage": {"code": "ERROR-500", "message": "서버 오류"}}

    with respx.mock(assert_all_called=True) as mock:
        mock.get(_station_url("강남")).mock(
            return_value=httpx.Response(200, json=payload)
        )

        async with httpx.AsyncClient() as client:
            subway_client = SubwayClient(client, _make_settings())
            with pytest.raises(SubwayApiUnavailable):
                await subway_client.fetch_arrivals("강남")


# ---------------------------------------------------------------------------
# 테스트: HTTP 5xx 응답
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_arrivals_http_5xx_raises_unavailable() -> None:
    """HTTP 500 응답 → SubwayApiUnavailable."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(_station_url("강남")).mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        async with httpx.AsyncClient() as client:
            subway_client = SubwayClient(client, _make_settings())
            with pytest.raises(SubwayApiUnavailable):
                await subway_client.fetch_arrivals("강남")


# ---------------------------------------------------------------------------
# 테스트: subway_api_key = None → 생성자에서 즉시 SubwayApiAuthFailed
# ---------------------------------------------------------------------------


def test_subway_client_raises_auth_failed_when_key_is_none() -> None:
    """subway_api_key = None → SubwayClient 생성 시 SubwayApiAuthFailed."""
    with pytest.raises(SubwayApiAuthFailed):
        SubwayClient(httpx.AsyncClient(), _make_settings(api_key=None))


def test_subway_client_raises_auth_failed_when_key_is_empty() -> None:
    """subway_api_key = '' → SubwayClient 생성 시 SubwayApiAuthFailed."""
    with pytest.raises(SubwayApiAuthFailed):
        SubwayClient(httpx.AsyncClient(), _make_settings(api_key=""))


# ---------------------------------------------------------------------------
# 테스트: 알 수 없는 subwayId → line_label = "알 수 없음"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_arrivals_unknown_subway_id_uses_unknown_label() -> None:
    """알 수 없는 subwayId → line_label = '알 수 없음'."""
    row = _sample_row(subway_id="9999")
    payload = _info_000_payload([row])

    with respx.mock(assert_all_called=True) as mock:
        mock.get(_station_url("강남")).mock(
            return_value=httpx.Response(200, json=payload)
        )

        async with httpx.AsyncClient() as client:
            subway_client = SubwayClient(client, _make_settings())
            result = await subway_client.fetch_arrivals("강남")

    assert len(result) == 1
    assert result[0].line_label == "알 수 없음"


# ---------------------------------------------------------------------------
# 테스트: trainLineNm, recptnDt 필드 파싱
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_row_to_arrival_parses_train_line_name_and_received_at() -> None:
    """trainLineNm, recptnDt 가 있는 row → train_line_name/received_at 올바르게 매핑."""
    row = _sample_row(
        train_line_nm="성수행(목적지역) - 구로디지털단지방면(다음역)",
        recptn_dt="2024-01-15 10:03:30",
    )
    payload = _info_000_payload([row])

    with respx.mock(assert_all_called=True) as mock:
        mock.get(_station_url("강남")).mock(
            return_value=httpx.Response(200, json=payload)
        )

        async with httpx.AsyncClient() as client:
            subway_client = SubwayClient(client, _make_settings())
            result = await subway_client.fetch_arrivals("강남")

    assert len(result) == 1
    arr = result[0]
    assert arr.train_line_name == "성수행(목적지역) - 구로디지털단지방면(다음역)"
    assert arr.received_at is not None
    # UTC 변환 검증: KST 10:03:30 = UTC 01:03:30
    assert arr.received_at.tzinfo == timezone.utc
    assert arr.received_at.hour == 1
    assert arr.received_at.minute == 3
    assert arr.received_at.second == 30


@pytest.mark.asyncio
async def test_row_to_arrival_empty_recptn_dt_gives_none_received_at() -> None:
    """recptnDt 가 빈 문자열이면 received_at=None."""
    row = _sample_row(recptn_dt="")
    payload = _info_000_payload([row])

    with respx.mock(assert_all_called=True) as mock:
        mock.get(_station_url("강남")).mock(
            return_value=httpx.Response(200, json=payload)
        )

        async with httpx.AsyncClient() as client:
            subway_client = SubwayClient(client, _make_settings())
            result = await subway_client.fetch_arrivals("강남")

    assert len(result) == 1
    assert result[0].received_at is None


# ---------------------------------------------------------------------------
# 테스트: _parse_recptn_dt 단위
# ---------------------------------------------------------------------------


def test_parse_recptn_dt_standard_format() -> None:
    """표준 포맷 '2024-01-15 10:03:30' → UTC aware datetime."""
    result = _parse_recptn_dt("2024-01-15 10:03:30")
    assert result is not None
    assert result.tzinfo == timezone.utc
    # KST 10:03:30 → UTC 01:03:30
    assert result.hour == 1
    assert result.minute == 3


def test_parse_recptn_dt_empty_string_returns_none() -> None:
    """빈 문자열 → None."""
    assert _parse_recptn_dt("") is None


def test_parse_recptn_dt_whitespace_only_returns_none() -> None:
    """공백만 있는 문자열 → None."""
    assert _parse_recptn_dt("   ") is None


def test_parse_recptn_dt_invalid_format_returns_none() -> None:
    """파싱 불가 문자열 → None."""
    assert _parse_recptn_dt("not-a-date") is None


def test_parse_recptn_dt_iso_format_fallback() -> None:
    """ISO 포맷 '2024-01-15T10:03:30' 도 파싱 가능."""
    result = _parse_recptn_dt("2024-01-15T10:03:30")
    assert result is not None
    assert result.tzinfo == timezone.utc
    assert result.hour == 1
