"""run_lunch_job (정기 스케줄) 단위 테스트.

회귀 가드:
1. 정시 윈도우 안 + 키 없음 → 큐 1건 + Redis dedup 키 SET.
2. dedup 키 존재 → skip (하루 1회).
3. now < notify_at → skip (아직 이름).
4. now >= notify_at + GRACE → skip (지각) + dedup 키 SET 안 됨.
5. 다음 날 (날짜 키 다름, time-machine 다른 날) → 다시 큐 적재.
6. 구독 2개 중 앞 구독 LunchCrawlerFailed + 뒤 구독 정상 → 뒤 구독 적재 + admin alert 1회.
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
import time_machine

from app.admin.alerts import CrawlerSource
from app.crawlers.lunch.client import LunchCorner, LunchMenu
from app.crawlers.lunch.exceptions import LunchCrawlerFailed
from app.crawlers.restaurants.client import Restaurant
from app.db.models import NotificationType
from app.notifications.lunch import worker as lunch_worker_module
from app.notifications.lunch.worker import (
    _DEDUP_TTL_SECONDS,
    run_lunch_job,
)
from app.scheduler.context import JobContext


# ---------------------------------------------------------------------------
# 헬퍼 dataclass / factory
# ---------------------------------------------------------------------------


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


class _FakeNotificationRepo:
    def __init__(self, pairs: list[tuple[_FakeNotification, _FakeUser]]) -> None:
        self._pairs = pairs

    async def list_active_subscriptions_with_user(
        self, type_: NotificationType
    ) -> list[tuple[_FakeNotification, _FakeUser]]:
        return self._pairs


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def commit(self) -> None:
        pass


class _FakeSessionMaker:
    def __init__(self, repo: _FakeNotificationRepo) -> None:
        self._repo = repo

    def __call__(self) -> "_FakeSession":
        return _FakeSession()


def _menu() -> LunchMenu:
    return LunchMenu(
        date_str="2026-05-26",
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
    pairs: list[tuple[_FakeNotification, _FakeUser]],
    *,
    lunch_result: Any = None,
    restaurants_result: Any = None,
    redis: fakeredis.aioredis.FakeRedis | None = None,
) -> tuple[JobContext, AsyncMock, AsyncMock, asyncio.Queue[Any]]:
    """테스트용 JobContext 를 만든다.

    lunch_result / restaurants_result 가 BaseException 인스턴스이면 side_effect 로 주입.
    """
    queue: asyncio.Queue[Any] = asyncio.Queue()
    settings = MagicMock()
    settings.admin_discord_ids = []

    if redis is None:
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    session_maker = MagicMock(side_effect=_FakeSession)

    ctx = JobContext(
        queue=queue,
        http_client=MagicMock(),
        session_maker=session_maker,
        settings=settings,
        redis_client=redis,
        in_flight_notification_ids=set(),
    )

    if lunch_result is None:
        lunch_result = _menu()
    if restaurants_result is None:
        restaurants_result = (_restaurant("소담"), _restaurant("일미"))

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

    return ctx, lunch_client.fetch_today_menu, restaurants_client.fetch_pool, queue


def _notification(
    nid: int = 1,
    uid: int = 10,
    notify_at: str = "12:00:00",
    recommend_count: int = 3,
    highlight: bool = True,
) -> tuple[_FakeNotification, _FakeUser]:
    n = _FakeNotification(
        id=nid,
        user_id=uid,
        type=NotificationType.LUNCH,
        enabled=True,
        config={
            "notify_at": notify_at,
            "recommend_count": recommend_count,
            "highlight_today_pick": highlight,
        },
    )
    u = _FakeUser(id=uid, discord_id=uid * 1000)
    return n, u


# ---------------------------------------------------------------------------
# 회귀 가드 1: 정시 윈도우 안 + 키 없음 → 큐 1건 + Redis SET
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel("2026-05-26 03:00:00+00:00", tick=False)
async def test_run_lunch_job_queues_task_in_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KST 12:00 = UTC 03:00. notify_at=12:00:00 → 윈도우 안 → 적재."""
    n, u = _notification(nid=1, notify_at="12:00:00")
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ctx, _, _, queue = _make_ctx([(n, u)], redis=redis)

    monkeypatch.setattr(
        "app.notifications.lunch.worker.NotificationRepository",
        lambda session: _FakeNotificationRepo([(n, u)]),
    )

    await run_lunch_job(ctx)

    assert queue.qsize() == 1
    task = await queue.get()
    assert task.notification_id == 1
    assert task.user_id == 10

    # dedup 키가 SET 되어야 한다.
    dedup_key = "lunch_sent:1:2026-05-26"
    val = await redis.get(dedup_key)
    assert val == "1"

    # TTL 이 설정되어 있어야 한다.
    ttl = await redis.ttl(dedup_key)
    assert ttl > 0


# ---------------------------------------------------------------------------
# 회귀 가드 2: dedup 키 존재 → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel("2026-05-26 03:00:00+00:00", tick=False)
async def test_run_lunch_job_skips_when_dedup_key_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """오늘 이미 발송한 경우(dedup 키 존재) → 큐에 아무것도 안 넣는다."""
    n, u = _notification(nid=2, notify_at="12:00:00")
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # 미리 dedup 키를 세팅한다.
    await redis.set("lunch_sent:2:2026-05-26", "1", ex=_DEDUP_TTL_SECONDS)

    ctx, fetch_menu, fetch_pool, queue = _make_ctx([(n, u)], redis=redis)

    monkeypatch.setattr(
        "app.notifications.lunch.worker.NotificationRepository",
        lambda session: _FakeNotificationRepo([(n, u)]),
    )

    await run_lunch_job(ctx)

    assert queue.qsize() == 0
    fetch_menu.assert_not_awaited()
    fetch_pool.assert_not_awaited()


# ---------------------------------------------------------------------------
# 회귀 가드 3: now < notify_at → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel("2026-05-26 02:00:00+00:00", tick=False)
async def test_run_lunch_job_skips_before_notify_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KST 11:00 = UTC 02:00. notify_at=12:00:00 → 아직 이름 → skip."""
    n, u = _notification(nid=3, notify_at="12:00:00")
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ctx, fetch_menu, fetch_pool, queue = _make_ctx([(n, u)], redis=redis)

    monkeypatch.setattr(
        "app.notifications.lunch.worker.NotificationRepository",
        lambda session: _FakeNotificationRepo([(n, u)]),
    )

    await run_lunch_job(ctx)

    assert queue.qsize() == 0
    fetch_menu.assert_not_awaited()
    fetch_pool.assert_not_awaited()

    # dedup 키도 SET 되지 않아야 한다.
    val = await redis.get("lunch_sent:3:2026-05-26")
    assert val is None


# ---------------------------------------------------------------------------
# 회귀 가드 4: now >= notify_at + GRACE → skip, dedup 키 SET 안 됨
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel("2026-05-26 03:10:00+00:00", tick=False)
async def test_run_lunch_job_skips_after_grace_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KST 12:10 = UTC 03:10. notify_at=12:00:00, GRACE=180s → 12:03 이후 → 지각 skip."""
    n, u = _notification(nid=4, notify_at="12:00:00")
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ctx, fetch_menu, fetch_pool, queue = _make_ctx([(n, u)], redis=redis)

    monkeypatch.setattr(
        "app.notifications.lunch.worker.NotificationRepository",
        lambda session: _FakeNotificationRepo([(n, u)]),
    )

    await run_lunch_job(ctx)

    assert queue.qsize() == 0
    fetch_menu.assert_not_awaited()
    fetch_pool.assert_not_awaited()

    # 지각 skip 이므로 dedup 키 미설정.
    val = await redis.get("lunch_sent:4:2026-05-26")
    assert val is None


# ---------------------------------------------------------------------------
# 회귀 가드 5: 다음 날 → 날짜 키 다름 → 다시 적재
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lunch_job_sends_again_next_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """오늘 발송 후 다음 날(날짜 키가 다름) → 다시 큐에 적재된다."""
    n, u = _notification(nid=5, notify_at="12:00:00")
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    # 어제 날짜 키가 이미 존재한다고 가정.
    await redis.set("lunch_sent:5:2026-05-25", "1", ex=_DEDUP_TTL_SECONDS)

    ctx, _, _, queue = _make_ctx([(n, u)], redis=redis)

    monkeypatch.setattr(
        "app.notifications.lunch.worker.NotificationRepository",
        lambda session: _FakeNotificationRepo([(n, u)]),
    )

    # 다음 날 KST 12:00 = UTC 03:00
    with time_machine.travel("2026-05-26 03:00:00+00:00", tick=False):
        await run_lunch_job(ctx)

        # dedup 키 검증은 frozen time 블록 안에서 수행해야 한다.
        # SET 시 TTL=25h 로 저장되며, 실제 벽시계 기준으로는 이미 만료될 수 있다.
        val = await redis.get("lunch_sent:5:2026-05-26")
        assert val == "1"

        ttl = await redis.ttl("lunch_sent:5:2026-05-26")
        assert ttl > 0

    assert queue.qsize() == 1
    task = await queue.get()
    assert task.notification_id == 5

# ---------------------------------------------------------------------------
# 회귀 가드 6: 앞 구독 LunchCrawlerFailed + 뒤 구독 정상 → 뒤 구독 적재 + admin 1회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel("2026-05-26 03:00:00+00:00", tick=False)
async def test_run_lunch_job_isolates_crawler_failure_and_alerts_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """앞 구독에서 LunchCrawlerFailed 발생 → 뒤 구독은 정상 적재 + admin alert 1회."""
    n1, u1 = _notification(nid=6, uid=10, notify_at="12:00:00")
    n2, u2 = _notification(nid=7, uid=20, notify_at="12:00:00")

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ctx, _, _, queue = _make_ctx([(n1, u1), (n2, u2)], redis=redis)

    call_count = [0]
    exc = LunchCrawlerFailed("playwright_timeout")

    async def _flaky_fetch_menu() -> LunchMenu:
        call_count[0] += 1
        if call_count[0] == 1:
            raise exc
        return _menu()

    ctx.lunch_client.fetch_today_menu = _flaky_fetch_menu  # type: ignore[attr-defined]

    monkeypatch.setattr(
        "app.notifications.lunch.worker.NotificationRepository",
        lambda session: _FakeNotificationRepo([(n1, u1), (n2, u2)]),
    )

    enqueue_calls: list[tuple[CrawlerSource, BaseException]] = []

    async def _fake_enqueue(
        queue: object,
        settings: object,
        source: CrawlerSource,
        exc: BaseException,
    ) -> None:
        enqueue_calls.append((source, exc))

    monkeypatch.setattr(
        lunch_worker_module,
        "enqueue_admin_alerts",
        _fake_enqueue,
    )

    await run_lunch_job(ctx)

    # 뒤 구독(n2)은 정상 적재되어야 한다.
    assert queue.qsize() == 1
    task = await queue.get()
    assert task.notification_id == 7

    # admin alert 는 틱당 1회만 발송.
    assert len(enqueue_calls) == 1
    assert enqueue_calls[0][0] == CrawlerSource.LUNCH

    # 앞 구독(n1) dedup 키는 SET 되지 않아야 한다(크롤러 실패라 재시도 가능하게).
    val1 = await redis.get("lunch_sent:6:2026-05-26")
    assert val1 is None

    # 뒤 구독(n2) dedup 키는 SET 되어야 한다.
    val2 = await redis.get("lunch_sent:7:2026-05-26")
    assert val2 == "1"


# ---------------------------------------------------------------------------
# 추가: clients None → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lunch_job_skips_when_clients_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    n, u = _notification(nid=9, notify_at="12:00:00")
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ctx, _, _, queue = _make_ctx([(n, u)], redis=redis)
    ctx.lunch_client = None
    ctx.restaurants_client = None

    await run_lunch_job(ctx)
    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# 추가: notify_at 파싱 실패 → skip + warn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel("2026-05-26 03:00:00+00:00", tick=False)
async def test_run_lunch_job_skips_invalid_notify_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    n, u = _notification(nid=10, notify_at="not-a-time")
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ctx, fetch_menu, _, queue = _make_ctx([(n, u)], redis=redis)

    monkeypatch.setattr(
        "app.notifications.lunch.worker.NotificationRepository",
        lambda session: _FakeNotificationRepo([(n, u)]),
    )

    await run_lunch_job(ctx)

    assert queue.qsize() == 0
    fetch_menu.assert_not_awaited()


# ---------------------------------------------------------------------------
# 추가: recommend_count 설정 반영 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel("2026-05-26 03:00:00+00:00", tick=False)
async def test_run_lunch_job_respects_recommend_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """recommend_count=2 이면 payload restaurants 2건."""
    n, u = _notification(nid=11, notify_at="12:00:00", recommend_count=2)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    pool = tuple(_restaurant(f"r{i}") for i in range(5))
    ctx, _, _, queue = _make_ctx([(n, u)], restaurants_result=pool, redis=redis)

    monkeypatch.setattr(
        "app.notifications.lunch.worker.NotificationRepository",
        lambda session: _FakeNotificationRepo([(n, u)]),
    )

    await run_lunch_job(ctx)

    assert queue.qsize() == 1
    task = await queue.get()
    # payload restaurants 는 recommend_count=2 만큼만 포함.
    assert len(task.payload["restaurants"]) == 2
