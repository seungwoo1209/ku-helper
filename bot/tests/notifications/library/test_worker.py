"""run_library_job 단위 테스트 — F-13 발송 + F-14 상태머신 회귀 가드 + F-15 긴급.

fakeredis 로 상태머신을, fake LibraryClient/Repository(monkeypatch)로 외부 의존을 대체한다.
APScheduler 를 거치지 않고 잡 함수를 직접 await 한다.
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import fakeredis.aioredis
import pytest

from app.admin.alerts import CrawlerSource
from app.crawlers.library.client import RoomSeats
from app.crawlers.library.exceptions import LibraryCrawlerFailed
from app.db.models import NotificationType
from app.notifications.library import worker as worker_module
from app.notifications.library.worker import (
    _state_key,
    run_immediate_send_library_job,
    run_library_job,
)
from app.notifications.lunch.repository import ImmediateSendRequestRow
from app.scheduler.context import JobContext


@dataclass
class _FakeNotification:
    id: int
    user_id: int
    type: NotificationType
    enabled: bool
    config: dict[str, Any]


@dataclass
class _FakeUser:
    id: int
    discord_id: int


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def commit(self) -> None:
        pass


class _FakeSessionMaker:
    def __call__(self) -> _FakeSession:
        return _FakeSession()


def _patch_repo(
    monkeypatch: pytest.MonkeyPatch,
    pairs: list[tuple[_FakeNotification, _FakeUser]],
) -> None:
    class _Repo:
        def __init__(self, session: Any) -> None:
            pass

        async def list_active_subscriptions_with_user(
            self, type_: NotificationType
        ) -> list[tuple[_FakeNotification, _FakeUser]]:
            return pairs

    monkeypatch.setattr(worker_module, "NotificationRepository", _Repo)


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict[int, RoomSeats],
    raises: Exception | None = None,
) -> None:
    class _Client:
        def __init__(self, http: Any, settings: Any, redis: Any = None) -> None:
            pass

        async def fetch_seats(self) -> dict[int, RoomSeats]:
            if raises is not None:
                raise raises
            return snapshot

    monkeypatch.setattr(worker_module, "LibraryClient", _Client)


def _ctx(redis: Any) -> JobContext:
    # redis_client 는 필수. 테스트에서는 fakeredis 또는 MagicMock 을 주입한다.
    r = (
        redis
        if redis is not None
        else fakeredis.aioredis.FakeRedis(decode_responses=True)
    )
    return JobContext(
        queue=asyncio.Queue(),
        http_client=MagicMock(),
        session_maker=_FakeSessionMaker(),
        settings=MagicMock(),
        redis_client=r,
    )


def _room(number: int, available: int, total: int = 400) -> RoomSeats:
    return RoomSeats(
        room_number=number, label=f"제{number}열람실", total=total, available=available
    )


def _notification(config: dict[str, Any]) -> tuple[_FakeNotification, _FakeUser]:
    return (
        _FakeNotification(
            id=7, user_id=42, type=NotificationType.LIBRARY, enabled=True, config=config
        ),
        _FakeUser(id=42, discord_id=999),
    )


@pytest.fixture
def redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.mark.asyncio
async def test_above_to_below_queues_and_sets_state(
    monkeypatch: pytest.MonkeyPatch, redis: fakeredis.aioredis.FakeRedis
) -> None:
    """직전 above(키 없음) + 현재 임계값 이하 → 큐 1건 + 상태 below."""
    pair = _notification({"reading_room_id": 1, "threshold": 20})
    _patch_repo(monkeypatch, [pair])
    _patch_client(monkeypatch, {1: _room(1, available=10)})
    ctx = _ctx(redis)

    await run_library_job(ctx)

    assert ctx.queue.qsize() == 1
    assert await redis.get(_state_key(42, 1)) == "below"


@pytest.mark.asyncio
async def test_below_to_below_does_not_resend(
    monkeypatch: pytest.MonkeyPatch, redis: fakeredis.aioredis.FakeRedis
) -> None:
    """직전 below + 여전히 임계값 이하 → 재발송 안 함 (F-14 핵심 가드)."""
    await redis.set(_state_key(42, 1), "below")
    pair = _notification({"reading_room_id": 1, "threshold": 20})
    _patch_repo(monkeypatch, [pair])
    _patch_client(monkeypatch, {1: _room(1, available=10)})
    ctx = _ctx(redis)

    await run_library_job(ctx)

    assert ctx.queue.qsize() == 0


@pytest.mark.asyncio
async def test_recovery_sets_above_without_send(
    monkeypatch: pytest.MonkeyPatch, redis: fakeredis.aioredis.FakeRedis
) -> None:
    """직전 below + 현재 임계값 위로 회복 → 큐 0건 + 상태 above."""
    await redis.set(_state_key(42, 1), "below")
    pair = _notification({"reading_room_id": 1, "threshold": 20})
    _patch_repo(monkeypatch, [pair])
    _patch_client(monkeypatch, {1: _room(1, available=300)})
    ctx = _ctx(redis)

    await run_library_job(ctx)

    assert ctx.queue.qsize() == 0
    assert await redis.get(_state_key(42, 1)) == "above"


@pytest.mark.asyncio
async def test_redis_state_persists_below_after_queue(
    monkeypatch: pytest.MonkeyPatch, redis: fakeredis.aioredis.FakeRedis
) -> None:
    """큐 적재 후 상태 키가 below 로 저장됨을 검증 (F-14 상태머신 지속성)."""
    pair = _notification({"reading_room_id": 1, "threshold": 20})
    _patch_repo(monkeypatch, [pair])
    _patch_client(monkeypatch, {1: _room(1, available=5)})
    ctx = _ctx(redis)

    await run_library_job(ctx)

    # 상태는 below 여야 하고 큐에 1건이 있어야 한다.
    assert ctx.queue.qsize() == 1
    state = await redis.get(_state_key(42, 1))
    assert state == "below"


@pytest.mark.asyncio
async def test_skips_when_room_absent(
    monkeypatch: pytest.MonkeyPatch, redis: fakeredis.aioredis.FakeRedis
) -> None:
    """구독 열람실이 현재 응답에 없으면(예: 제4) skip."""
    pair = _notification({"reading_room_id": 4, "threshold": 20})
    _patch_repo(monkeypatch, [pair])
    _patch_client(monkeypatch, {1: _room(1, available=10)})
    ctx = _ctx(redis)

    await run_library_job(ctx)

    assert ctx.queue.qsize() == 0


@pytest.mark.asyncio
async def test_urgent_payload_flag(
    monkeypatch: pytest.MonkeyPatch, redis: fakeredis.aioredis.FakeRedis
) -> None:
    """잔여 ≤ urgent_threshold 면 task.payload.is_urgent True (F-15)."""
    pair = _notification({"reading_room_id": 1, "threshold": 20, "urgent_threshold": 5})
    _patch_repo(monkeypatch, [pair])
    _patch_client(monkeypatch, {1: _room(1, available=3)})
    ctx = _ctx(redis)

    await run_library_job(ctx)

    task = ctx.queue.get_nowait()
    assert task.payload["is_urgent"] is True
    assert task.notification_id == 7
    assert task.discord_id == 999


@pytest.mark.asyncio
async def test_crawler_failure_is_swallowed(
    monkeypatch: pytest.MonkeyPatch, redis: fakeredis.aioredis.FakeRedis
) -> None:
    """크롤러 실패 시 예외를 swallow 하고 큐는 비어 있어야 한다."""
    pair = _notification({"reading_room_id": 1, "threshold": 20})
    _patch_repo(monkeypatch, [pair])
    _patch_client(monkeypatch, {}, raises=LibraryCrawlerFailed("boom"))
    ctx = _ctx(redis)

    await run_library_job(ctx)

    assert ctx.queue.qsize() == 0


@pytest.mark.asyncio
async def test_crawler_failure_calls_admin_alert(
    monkeypatch: pytest.MonkeyPatch, redis: fakeredis.aioredis.FakeRedis
) -> None:
    """크롤러 실패 시 enqueue_admin_alerts 가 LIBRARY source 로 1회 호출."""
    pair = _notification({"reading_room_id": 1, "threshold": 20})
    _patch_repo(monkeypatch, [pair])
    _patch_client(monkeypatch, {}, raises=LibraryCrawlerFailed("boom"))
    ctx = _ctx(redis)

    enqueue_calls: list[tuple[object, ...]] = []

    async def _fake_enqueue(
        queue: object,
        settings: object,
        source: CrawlerSource,
        exc: BaseException,
    ) -> None:
        enqueue_calls.append((source, exc))

    monkeypatch.setattr(worker_module, "enqueue_admin_alerts", _fake_enqueue)

    await run_library_job(ctx)

    assert len(enqueue_calls) == 1
    assert enqueue_calls[0][0] == CrawlerSource.LIBRARY


# ---------------------------------------------------------------------------
# 즉시 발송 (run_immediate_send_library_job)
# ---------------------------------------------------------------------------


def _patch_immediate_repo(
    monkeypatch: pytest.MonkeyPatch, rows: list[ImmediateSendRequestRow]
) -> None:
    class _Repo:
        def __init__(self, session: Any) -> None:
            pass

        async def list_pending(
            self, type_: NotificationType, limit: int = 50
        ) -> list[ImmediateSendRequestRow]:
            return rows

    monkeypatch.setattr(worker_module, "ImmediateSendRequestRepository", _Repo)


def _patch_history(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    class _Hist:
        def __init__(self, session: Any) -> None:
            pass

        async def insert_result(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(worker_module, "NotificationHistoryRepository", _Hist)
    return calls


def _pending_row(
    payload: dict[str, Any], request_id: int = 5
) -> ImmediateSendRequestRow:
    return ImmediateSendRequestRow(
        id=request_id, user_id=42, discord_id=999, payload=payload
    )


@pytest.mark.asyncio
async def test_immediate_pending_row_queues(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_immediate_repo(monkeypatch, [_pending_row({"reading_room_id": 1})])
    _patch_client(monkeypatch, {1: _room(1, available=50)})
    _patch_history(monkeypatch)
    ctx = _ctx(None)

    await run_immediate_send_library_job(ctx)

    assert ctx.queue.qsize() == 1
    task = ctx.queue.get_nowait()
    assert task.immediate_send_request_id == 5
    assert task.notification_id is None


@pytest.mark.asyncio
async def test_immediate_room_absent_inserts_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """요청 열람실이 현재 응답에 없으면 FAILED history INSERT + 큐 0건."""
    _patch_immediate_repo(monkeypatch, [_pending_row({"reading_room_id": 2})])
    _patch_client(monkeypatch, {1: _room(1, available=50)})
    calls = _patch_history(monkeypatch)
    ctx = _ctx(None)

    await run_immediate_send_library_job(ctx)

    assert ctx.queue.qsize() == 0
    assert len(calls) == 1
    assert calls[0]["failure_reason"] == "room_absent"


@pytest.mark.asyncio
async def test_immediate_crawler_failure_inserts_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_immediate_repo(monkeypatch, [_pending_row({"reading_room_id": 1})])
    _patch_client(monkeypatch, {}, raises=LibraryCrawlerFailed("boom"))
    calls = _patch_history(monkeypatch)
    ctx = _ctx(None)

    await run_immediate_send_library_job(ctx)

    assert ctx.queue.qsize() == 0
    assert len(calls) == 1
    assert calls[0]["failure_reason"] == "LIBRARY_CRAWLER_FAILED"


@pytest.mark.asyncio
async def test_immediate_inflight_skips_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_immediate_repo(monkeypatch, [_pending_row({"reading_room_id": 1})])
    _patch_client(monkeypatch, {1: _room(1, available=50)})
    _patch_history(monkeypatch)
    ctx = _ctx(None)
    ctx.immediate_send_inflight.add(5)

    await run_immediate_send_library_job(ctx)

    assert ctx.queue.qsize() == 0


@pytest.mark.asyncio
async def test_immediate_send_library_calls_admin_alert_on_crawler_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """즉시 발송 경로에서 LibraryCrawlerFailed 발생 시 enqueue_admin_alerts 가
    CrawlerSource.LIBRARY 로 1회 호출되어야 한다 (per-row catch 회귀 가드)."""
    _patch_immediate_repo(monkeypatch, [_pending_row({"reading_room_id": 1})])
    _patch_client(monkeypatch, {}, raises=LibraryCrawlerFailed("boom"))
    _patch_history(monkeypatch)
    ctx = _ctx(None)

    enqueue_calls: list[tuple[object, ...]] = []

    async def _fake_enqueue(
        queue: object,
        settings: object,
        source: CrawlerSource,
        exc: BaseException,
    ) -> None:
        enqueue_calls.append((source, exc))

    monkeypatch.setattr(worker_module, "enqueue_admin_alerts", _fake_enqueue)

    await run_immediate_send_library_job(ctx)

    assert len(enqueue_calls) == 1
    assert enqueue_calls[0][0] == CrawlerSource.LIBRARY
    # FAILED INSERT 도 실행되어야 한다.
    assert ctx.queue.qsize() == 0
    assert ctx.immediate_send_inflight == set()
