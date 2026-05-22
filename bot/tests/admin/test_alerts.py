"""F-22 admin/alerts.py 단위 테스트.

노이즈 가드(카운터/쿨다운)는 삭제됨. single-trigger 정책만 검증한다.
"""

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.admin.alerts import (
    CrawlerSource,
    build_admin_failure_embed,
    enqueue_admin_alerts,
)
from app.notifications.sender import SendDmTask


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


def _make_settings(admin_ids: list[int]) -> Any:
    s = MagicMock()
    s.admin_discord_ids = admin_ids
    return s


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
        occurred_at=occurred_at,
    )
    d = embed.to_dict()

    assert d["color"] == 0xE74C3C
    assert "subway" in d["title"]
    assert "🚨" in d["title"]


def test_build_admin_failure_embed_fields_present() -> None:
    """오류 요약·발생 시각 KST 필드가 존재하고, '횟수' 필드는 없어야 한다."""
    from datetime import datetime, timezone

    occurred_at = datetime(2026, 5, 22, 1, 0, 0, tzinfo=timezone.utc)
    embed = build_admin_failure_embed(
        source=CrawlerSource.LUNCH,
        error_message="playwright timeout",
        occurred_at=occurred_at,
    )
    d = embed.to_dict()

    field_names = {f["name"] for f in d["fields"]}
    assert "오류 요약" in field_names
    assert "발생 시각 KST" in field_names
    # 노이즈 가드 삭제로 횟수 필드는 제거됨.
    assert "횟수" not in field_names


def test_build_admin_failure_embed_error_truncated() -> None:
    """200자를 초과하는 오류 메시지는 200자로 절단되어야 한다."""
    from datetime import datetime, timezone

    long_error = "x" * 300
    occurred_at = datetime(2026, 5, 22, 0, 0, 0, tzinfo=timezone.utc)
    embed = build_admin_failure_embed(
        source=CrawlerSource.LIBRARY,
        error_message=long_error,
        occurred_at=occurred_at,
    )
    d = embed.to_dict()

    excerpt_field = next(f for f in d["fields"] if f["name"] == "오류 요약")
    assert len(excerpt_field["value"]) <= 200


# ---------------------------------------------------------------------------
# enqueue_admin_alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_admin_alerts_single_trigger_enqueues_immediately() -> None:
    """실패 1회 → 즉시 admin_ids 길이만큼 task 적재 (single-trigger)."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    admin_ids = [111111, 222222]
    settings = _make_settings(admin_ids)
    exc = RuntimeError("critical failure")

    await enqueue_admin_alerts(queue, settings, CrawlerSource.SUBWAY, exc)

    assert queue.qsize() == len(admin_ids)


@pytest.mark.asyncio
async def test_enqueue_admin_alerts_task_fields() -> None:
    """적재된 task 의 FK 필드와 payload 키를 검증한다."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    admin_ids = [999888]
    settings = _make_settings(admin_ids)
    exc = RuntimeError("db connection lost")

    await enqueue_admin_alerts(queue, settings, CrawlerSource.LIBRARY, exc)

    task = queue.get_nowait()
    assert task.notification_id is None
    assert task.immediate_send_request_id is None
    assert task.discord_id == 999888
    assert task.user_id == 999888
    # payload 키 검증 — count 키는 없어야 한다.
    assert task.payload["source"] == CrawlerSource.LIBRARY.value
    assert task.payload["code"] == "RuntimeError"
    assert "error_excerpt" in task.payload
    assert "count" not in task.payload


@pytest.mark.asyncio
async def test_enqueue_admin_alerts_no_admin_ids_enqueues_nothing() -> None:
    """admin_discord_ids 가 비어 있으면 task 0건 + 예외 없음."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    settings = _make_settings([])
    exc = RuntimeError("error")

    await enqueue_admin_alerts(queue, settings, CrawlerSource.SUBWAY, exc)

    assert queue.qsize() == 0


@pytest.mark.asyncio
async def test_enqueue_admin_alerts_multiple_calls_each_enqueue() -> None:
    """2회 연속 호출 → 매 호출마다 즉시 큐 적재 (카운터/쿨다운 없음)."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    settings = _make_settings([111111])
    exc = RuntimeError("persistent error")

    await enqueue_admin_alerts(queue, settings, CrawlerSource.LUNCH, exc)
    await enqueue_admin_alerts(queue, settings, CrawlerSource.LUNCH, exc)

    # 2회 호출 × 1개 admin_id = 2건
    assert queue.qsize() == 2
