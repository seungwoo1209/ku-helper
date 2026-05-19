"""run_immediate_send_lunch_job 단위 테스트."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.crawlers.lunch.client import LunchCorner, LunchMenu
from app.crawlers.lunch.exceptions import LunchCrawlerFailed
from app.crawlers.restaurants.client import Restaurant
from app.notifications.lunch.repository import ImmediateSendRequestRow
from app.notifications.lunch.worker import run_immediate_send_lunch_job
from app.scheduler.context import JobContext


def _menu() -> LunchMenu:
    return LunchMenu(
        date_str="2026-05-19",
        weekday="화",
        cafeteria_name="건국대 학생식당",
        corners=(LunchCorner(name="한식", time="11~13", meal="점심", menus=("백반",)),),
        menus=("백반",),
    )


def _restaurant(name: str) -> Restaurant:
    return Restaurant(
        name=name, category="한식", address="광진구", link=f"https://x/{name}"
    )


def _make_ctx(
    rows: list[ImmediateSendRequestRow],
    *,
    lunch_result: Any,
    restaurants_result: Any,
) -> tuple[JobContext, AsyncMock, AsyncMock, asyncio.Queue[Any]]:
    queue: asyncio.Queue[Any] = asyncio.Queue()
    settings = MagicMock()
    session_maker = MagicMock()

    # session_maker() async context returns mock session — repository will be
    # constructed but we patch list_pending via monkeypatching the module.
    ctx = JobContext(
        queue=queue,
        http_client=MagicMock(),
        session_maker=session_maker,
        settings=settings,
        in_flight_notification_ids=set(),
    )

    lunch_client = MagicMock()
    lunch_client.fetch_today_menu = AsyncMock(
        return_value=lunch_result
        if not isinstance(lunch_result, BaseException)
        else None,
        side_effect=lunch_result if isinstance(lunch_result, BaseException) else None,
    )
    restaurants_client = MagicMock()
    restaurants_client.fetch_pool = AsyncMock(
        return_value=restaurants_result
        if not isinstance(restaurants_result, BaseException)
        else None,
        side_effect=restaurants_result
        if isinstance(restaurants_result, BaseException)
        else None,
    )
    ctx.lunch_client = lunch_client
    ctx.restaurants_client = restaurants_client
    ctx.immediate_send_inflight = set()

    # repository.list_pending 결과를 고정.
    async def _fake_list_pending(*a: Any, **k: Any) -> list[ImmediateSendRequestRow]:
        return rows

    return ctx, lunch_client.fetch_today_menu, restaurants_client.fetch_pool, queue


@pytest.mark.asyncio
async def test_run_immediate_send_lunch_job_queues_task_on_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        ImmediateSendRequestRow(id=10, user_id=1, discord_id=99, payload={}),
    ]
    pool = (_restaurant("소담"), _restaurant("일미"), _restaurant("분식"))
    ctx, _, _, queue = _make_ctx(rows, lunch_result=_menu(), restaurants_result=pool)

    async def _fake_list_pending(self: Any, type_: Any, limit: int = 50) -> list[Any]:
        return rows

    monkeypatch.setattr(
        "app.notifications.lunch.repository.ImmediateSendRequestRepository.list_pending",
        _fake_list_pending,
    )
    # session_maker async context manager.
    fake_session = AsyncMock()
    ctx.session_maker.return_value.__aenter__.return_value = fake_session  # type: ignore[attr-defined]
    ctx.session_maker.return_value.__aexit__.return_value = False  # type: ignore[attr-defined]

    await run_immediate_send_lunch_job(ctx)

    assert queue.qsize() == 1
    task = await queue.get()
    assert task.immediate_send_request_id == 10
    assert task.user_id == 1
    assert task.discord_id == 99
    assert task.notification_id is None
    assert 10 in ctx.immediate_send_inflight


@pytest.mark.asyncio
async def test_run_immediate_send_lunch_job_skips_when_clients_missing() -> None:
    ctx, _, _, queue = _make_ctx([], lunch_result=_menu(), restaurants_result=())
    ctx.lunch_client = None
    ctx.restaurants_client = None

    await run_immediate_send_lunch_job(ctx)
    assert queue.qsize() == 0


@pytest.mark.asyncio
async def test_run_immediate_send_lunch_job_dedup_within_same_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        ImmediateSendRequestRow(id=20, user_id=2, discord_id=100, payload={}),
    ]
    pool = (_restaurant("소담"),)
    ctx, fetch_menu, fetch_pool, queue = _make_ctx(
        rows, lunch_result=_menu(), restaurants_result=pool
    )
    # 이미 in-flight 에 들어 있으면 skip 되어야 함.
    ctx.immediate_send_inflight = {20}

    async def _fake_list_pending(self: Any, type_: Any, limit: int = 50) -> list[Any]:
        return rows

    monkeypatch.setattr(
        "app.notifications.lunch.repository.ImmediateSendRequestRepository.list_pending",
        _fake_list_pending,
    )
    fake_session = AsyncMock()
    ctx.session_maker.return_value.__aenter__.return_value = fake_session  # type: ignore[attr-defined]
    ctx.session_maker.return_value.__aexit__.return_value = False  # type: ignore[attr-defined]

    await run_immediate_send_lunch_job(ctx)

    assert queue.qsize() == 0
    fetch_menu.assert_not_awaited()
    fetch_pool.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_immediate_send_lunch_job_writes_failed_history_on_crawler_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        ImmediateSendRequestRow(id=30, user_id=3, discord_id=101, payload={}),
    ]
    ctx, _, _, queue = _make_ctx(
        rows,
        lunch_result=LunchCrawlerFailed("playwright_timeout: test"),
        restaurants_result=(),
    )

    async def _fake_list_pending(self: Any, type_: Any, limit: int = 50) -> list[Any]:
        return rows

    monkeypatch.setattr(
        "app.notifications.lunch.repository.ImmediateSendRequestRepository.list_pending",
        _fake_list_pending,
    )

    # 첫 session 호출은 list_pending 용, 두 번째는 FAILED INSERT 용.
    failed_inserts: list[dict[str, Any]] = []

    class _FakeHistoryRepo:
        def __init__(self, session: Any) -> None:
            pass

        async def insert_result(self, **kwargs: Any) -> None:
            failed_inserts.append(kwargs)

    monkeypatch.setattr(
        "app.notifications.lunch.worker.NotificationHistoryRepository",
        _FakeHistoryRepo,
    )

    fake_session = AsyncMock()
    ctx.session_maker.return_value.__aenter__.return_value = fake_session  # type: ignore[attr-defined]
    ctx.session_maker.return_value.__aexit__.return_value = False  # type: ignore[attr-defined]

    await run_immediate_send_lunch_job(ctx)

    assert queue.qsize() == 0
    assert len(failed_inserts) == 1
    assert failed_inserts[0]["immediate_send_request_id"] == 30
    assert 30 not in ctx.immediate_send_inflight
