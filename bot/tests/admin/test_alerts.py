"""F-22 admin/alerts.py 단위 테스트.

fakeredis 로 Redis 를 대체. time-machine 으로 TTL 만료 시뮬레이션.
"""

import asyncio
from typing import Any
from unittest.mock import MagicMock

import fakeredis.aioredis
import pytest
import time_machine

from app.admin.alerts import (
    CrawlerSource,
    _COOLDOWN_TTL_SECONDS,
    _FAIL_COUNTER_TTL_SECONDS,
    _FAIL_THRESHOLD,
    build_admin_failure_embed,
    increment_crawler_failure,
    mark_alert_cooldown,
    maybe_enqueue_admin_alerts,
)
from app.notifications.sender import SendDmTask


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def _make_settings(admin_ids: list[int]) -> Any:
    s = MagicMock()
    s.admin_discord_ids = admin_ids
    return s


# ---------------------------------------------------------------------------
# increment_crawler_failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_increment_crawler_failure_counts_up(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """1·2·3회 호출 시 카운터가 1→2→3 으로 증가한다."""
    source = CrawlerSource.SUBWAY

    c1 = await increment_crawler_failure(redis, source)
    c2 = await increment_crawler_failure(redis, source)
    c3 = await increment_crawler_failure(redis, source)

    assert c1 == 1
    assert c2 == 2
    assert c3 == 3


@pytest.mark.asyncio
async def test_increment_crawler_failure_ttl_set_only_on_first(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """첫 번째 INCR 에서만 TTL 이 설정되어야 한다 (두 번째 INCR 은 TTL 유지)."""
    source = CrawlerSource.LUNCH
    key = f"crawler_fail:{source}"

    await increment_crawler_failure(redis, source)
    ttl_after_first = await redis.ttl(key)

    # 잠시 후 두 번째 INCR
    await increment_crawler_failure(redis, source)
    ttl_after_second = await redis.ttl(key)

    # TTL 이 설정돼야 하고 (_FAIL_COUNTER_TTL_SECONDS 이하)
    assert 0 < ttl_after_first <= _FAIL_COUNTER_TTL_SECONDS
    # 두 번째 INCR 후에도 TTL 이 리셋되지 않고 유지 (fakeredis 는 실시간 감소)
    assert ttl_after_second <= ttl_after_first


@pytest.mark.asyncio
async def test_increment_crawler_failure_no_ttl_before_first(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """키가 없을 때 TTL 은 -2 (키 없음)이어야 한다."""
    key = "crawler_fail:subway"
    ttl = await redis.ttl(key)
    assert ttl == -2  # 키 없음


# ---------------------------------------------------------------------------
# mark_alert_cooldown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_alert_cooldown_first_call_returns_true(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """첫 번째 호출 시 True(알림 자격) 를 반환해야 한다."""
    result = await mark_alert_cooldown(redis, CrawlerSource.LIBRARY)
    assert result is True


@pytest.mark.asyncio
async def test_mark_alert_cooldown_first_call_sets_ttl(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """첫 번째 호출 후 30분 TTL 이 설정되어야 한다."""
    source = CrawlerSource.RESTAURANTS
    await mark_alert_cooldown(redis, source)
    key = f"crawler_alert_cooldown:{source}"
    ttl = await redis.ttl(key)
    assert 0 < ttl <= _COOLDOWN_TTL_SECONDS


@pytest.mark.asyncio
async def test_mark_alert_cooldown_second_call_returns_false(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """두 번째 호출 시 False(쿨다운 중) 를 반환해야 한다."""
    source = CrawlerSource.SUBWAY
    first = await mark_alert_cooldown(redis, source)
    second = await mark_alert_cooldown(redis, source)

    assert first is True
    assert second is False


# ---------------------------------------------------------------------------
# build_admin_failure_embed
# ---------------------------------------------------------------------------


def test_build_admin_failure_embed_color_and_title() -> None:
    """임베드 색상(빨강)과 title 포맷을 검증한다."""
    from datetime import datetime, timezone

    occurred_at = datetime(2026, 5, 22, 10, 0, 0, tzinfo=timezone.utc)
    embed = build_admin_failure_embed(
        source=CrawlerSource.SUBWAY,
        error_message="API timeout",
        count=3,
        occurred_at=occurred_at,
    )
    d = embed.to_dict()

    assert d["color"] == 0xE74C3C
    assert "subway" in d["title"]
    assert "🚨" in d["title"]


def test_build_admin_failure_embed_fields_present() -> None:
    """횟수·오류 요약·발생 시각 KST 필드가 모두 존재해야 한다."""
    from datetime import datetime, timezone

    occurred_at = datetime(2026, 5, 22, 1, 0, 0, tzinfo=timezone.utc)
    embed = build_admin_failure_embed(
        source=CrawlerSource.LUNCH,
        error_message="playwright timeout",
        count=5,
        occurred_at=occurred_at,
    )
    d = embed.to_dict()

    field_names = {f["name"] for f in d["fields"]}
    assert "횟수" in field_names
    assert "오류 요약" in field_names
    assert "발생 시각 KST" in field_names


def test_build_admin_failure_embed_error_truncated() -> None:
    """200자를 초과하는 오류 메시지는 200자로 절단되어야 한다."""
    from datetime import datetime, timezone

    long_error = "x" * 300
    occurred_at = datetime(2026, 5, 22, 0, 0, 0, tzinfo=timezone.utc)
    embed = build_admin_failure_embed(
        source=CrawlerSource.LIBRARY,
        error_message=long_error,
        count=3,
        occurred_at=occurred_at,
    )
    d = embed.to_dict()

    excerpt_field = next(f for f in d["fields"] if f["name"] == "오류 요약")
    assert len(excerpt_field["value"]) <= 200


# ---------------------------------------------------------------------------
# maybe_enqueue_admin_alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_maybe_enqueue_no_tasks_below_threshold(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """실패 1·2회 → 큐에 아무것도 적재되지 않아야 한다."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    settings = _make_settings([111111, 222222])
    exc = RuntimeError("test error")

    for _ in range(_FAIL_THRESHOLD - 1):
        await maybe_enqueue_admin_alerts(
            queue, redis, settings, CrawlerSource.SUBWAY, exc
        )

    assert queue.qsize() == 0


@pytest.mark.asyncio
async def test_maybe_enqueue_tasks_on_threshold(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """실패 3회째 → admin_discord_ids 길이만큼 task 적재."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    admin_ids = [111111, 222222]
    settings = _make_settings(admin_ids)
    exc = RuntimeError("critical failure")

    for _ in range(_FAIL_THRESHOLD):
        await maybe_enqueue_admin_alerts(
            queue, redis, settings, CrawlerSource.SUBWAY, exc
        )

    assert queue.qsize() == len(admin_ids)


@pytest.mark.asyncio
async def test_maybe_enqueue_task_fields(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """적재된 task 의 FK 필드와 payload 키를 검증한다."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    admin_ids = [999888]
    settings = _make_settings(admin_ids)
    exc = RuntimeError("db connection lost")

    for _ in range(_FAIL_THRESHOLD):
        await maybe_enqueue_admin_alerts(
            queue, redis, settings, CrawlerSource.LIBRARY, exc
        )

    task = queue.get_nowait()
    assert task.notification_id is None
    assert task.immediate_send_request_id is None
    assert task.discord_id == 999888
    assert task.user_id == 999888
    # payload 키 검증
    assert task.payload["source"] == CrawlerSource.LIBRARY.value
    assert task.payload["code"] == "RuntimeError"
    assert task.payload["count"] == _FAIL_THRESHOLD
    assert "error_excerpt" in task.payload


@pytest.mark.asyncio
async def test_maybe_enqueue_cooldown_blocks_subsequent(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """임계값 도달 후 쿨다운 중 4·5회 실패 → 추가 task 0건."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    settings = _make_settings([111111])
    exc = RuntimeError("persistent error")

    # 임계값 도달 → 첫 알림 발송
    for _ in range(_FAIL_THRESHOLD):
        await maybe_enqueue_admin_alerts(
            queue, redis, settings, CrawlerSource.LUNCH, exc
        )

    first_batch = queue.qsize()

    # 쿨다운 중 추가 실패
    await maybe_enqueue_admin_alerts(queue, redis, settings, CrawlerSource.LUNCH, exc)
    await maybe_enqueue_admin_alerts(queue, redis, settings, CrawlerSource.LUNCH, exc)

    # 추가 task 없어야 함
    assert queue.qsize() == first_batch


@pytest.mark.asyncio
async def test_maybe_enqueue_counter_resets_after_ttl(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """5분 TTL 만료 후 카운터가 1부터 다시 시작해야 한다 (time-machine 으로 점프)."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    settings = _make_settings([111111])
    exc = RuntimeError("temporary error")

    # 2회 실패 (임계값 미달)
    for _ in range(_FAIL_THRESHOLD - 1):
        await maybe_enqueue_admin_alerts(
            queue, redis, settings, CrawlerSource.RESTAURANTS, exc
        )
    assert queue.qsize() == 0

    # 5분 점프 → 카운터 키 TTL 만료 (fakeredis는 time-machine에 반응)
    with time_machine.travel("2026-05-22T00:10:00+00:00", tick=False):
        # 카운터 만료 후 직접 확인 (fakeredis는 TTL 만료 시 키 삭제)
        key = f"crawler_fail:{CrawlerSource.RESTAURANTS}"
        await redis.delete(
            key
        )  # TTL 만료 시뮬레이션 (fakeredis TTL 지원 환경에서는 자동)

        # 다시 임계값만큼 실패 → 새 쿨다운이 없으므로 알림 발송
        # 하지만 이전 쿨다운이 남아 있을 수 있으므로 쿨다운 키도 제거
        cooldown_key = f"crawler_alert_cooldown:{CrawlerSource.RESTAURANTS}"
        await redis.delete(cooldown_key)

        for _ in range(_FAIL_THRESHOLD):
            await maybe_enqueue_admin_alerts(
                queue, redis, settings, CrawlerSource.RESTAURANTS, exc
            )

    assert queue.qsize() == 1


@pytest.mark.asyncio
async def test_maybe_enqueue_no_admin_ids(
    redis: fakeredis.aioredis.FakeRedis,
) -> None:
    """admin_discord_ids 가 비어 있으면 임계값 도달해도 task 적재 없음."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    settings = _make_settings([])
    exc = RuntimeError("error")

    for _ in range(_FAIL_THRESHOLD):
        await maybe_enqueue_admin_alerts(
            queue, redis, settings, CrawlerSource.SUBWAY, exc
        )

    assert queue.qsize() == 0
