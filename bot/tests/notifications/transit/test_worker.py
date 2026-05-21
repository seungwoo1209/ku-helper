"""run_transit_job 단위 테스트 (F-07 recurring + F-06 arrival 모드) + run_immediate_send_transit_job.

time-machine 으로 시각 고정, fake SubwayClient/Repository 를 monkeypatch 로 주입.
APScheduler 를 거치지 않고 잡 함수를 직접 await 한다.

시각 고정 규칙:
- freeze 시각은 KST 오프셋(+09:00)을 명시한 ISO 문자열 사용.
- KST 08:00 = UTC 23:00 전일. 윈도우 비교가 KST 기준인지 검증할 때 이 차이를 이용한다.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import fakeredis.aioredis
import httpx
import pytest
import time_machine

from app.crawlers.subway.client import SubwayArrival
from app.crawlers.subway.exceptions import SubwayApiUnavailable
from app.db.models import NotificationDeliveryStatus, NotificationType
from app.notifications.lunch.repository import ImmediateSendRequestRow
from app.notifications.sender import SendDmTask
from app.notifications.transit.worker import (
    _ARRIVAL_REDIS_KEY_TEMPLATE,
    run_immediate_send_transit_job,
    run_transit_job,
)
from app.scheduler.context import JobContext


# ---------------------------------------------------------------------------
# 헬퍼 dataclass / fake
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


class _FakeHistoryRepo:
    def __init__(self, last_sent_at: datetime | None = None) -> None:
        self._last_sent_at = last_sent_at

    async def get_last_sent_at(
        self,
        notification_id: int,
        status: NotificationDeliveryStatus,
    ) -> datetime | None:
        return self._last_sent_at


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def commit(self) -> None:
        pass


class _FakeSessionMaker:
    def __call__(self) -> "_FakeSession":
        return _FakeSession()


class _FakeSubwayClient:
    def __init__(self, arrivals: list[SubwayArrival], call_count: list[int]) -> None:
        self._arrivals = arrivals
        self._call_count = call_count

    async def fetch_arrivals(self, station_name: str) -> list[SubwayArrival]:
        self._call_count.append(1)
        return self._arrivals


class _RaisingSubwayClient:
    async def fetch_arrivals(self, station_name: str) -> list[SubwayArrival]:
        raise SubwayApiUnavailable()


def _make_arrival(
    direction: str = "상행",
    seconds: int = 120,
    train_no: str = "2001",
    line_label: str = "2호선",
) -> SubwayArrival:
    return SubwayArrival(
        station_name="강남",
        subway_id="1002",
        line_label=line_label,
        direction=direction,
        headed_for="성수",
        arrival_message="도착",
        arrival_message_detail="강남 도착",
        arrival_seconds=seconds,
        train_no=train_no,
        arvl_code=1,
        train_type="일반",
        train_line_name="",
        received_at=None,
    )


def _make_ctx(
    queue: asyncio.Queue[SendDmTask] | None = None,
    in_flight: set[int] | None = None,
    redis_client: Any = None,
) -> JobContext:
    from pydantic import SecretStr

    settings = MagicMock()
    settings.subway_api_key = SecretStr("test-key")

    # redis_client 는 필수. None 이 전달되면 fakeredis 로 대체한다.
    r = (
        redis_client
        if redis_client is not None
        else fakeredis.aioredis.FakeRedis(decode_responses=True)
    )

    return JobContext(
        queue=queue or asyncio.Queue(),
        http_client=httpx.AsyncClient(),
        session_maker=_FakeSessionMaker(),  # type: ignore[arg-type]
        settings=settings,
        redis_client=r,
        in_flight_notification_ids=in_flight if in_flight is not None else set(),
    )


# KST 2026-05-19 10:00:00 = UTC 2026-05-19 01:00:00
_FIXED_KST = "2026-05-19T10:00:00+09:00"
# UTC equivalent for use in last_sent_at calculations
_FIXED_NOW_UTC = datetime(2026, 5, 19, 1, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# 케이스 1: 윈도우 안 + 마지막 발송 없음 → 큐 1건 + in_flight set 1건
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_FIXED_KST, tick=False)
async def test_recurring_no_history_enqueues_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """윈도우 내, 이력 없음 → 큐에 1건 적재 + in_flight 에 notification_id 추가."""
    notif = _FakeNotification(
        id=10,
        user_id=1,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "recurring",
            "station_name": "강남",
            "line": "2호선",
            "repeat_interval_minutes": 5,
        },
    )
    user = _FakeUser(id=1, discord_id=9999)

    call_count: list[int] = []
    fake_client = _FakeSubwayClient([_make_arrival()], call_count)

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    in_flight: set[int] = set()
    ctx = _make_ctx(queue=queue, in_flight=in_flight)

    with (
        monkeypatch.context() as m,
    ):
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: fake_client,
        )

        await run_transit_job(ctx)

    assert queue.qsize() == 1
    assert 10 in in_flight
    task = await queue.get()
    assert task.notification_id == 10
    assert task.user_id == 1
    assert task.discord_id == 9999


# ---------------------------------------------------------------------------
# 케이스 2: 윈도우 안 + 마지막 발송 < interval → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_FIXED_KST, tick=False)
async def test_recurring_recent_history_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """마지막 발송이 interval 미만 전 → skip (큐 비어 있음)."""
    notif = _FakeNotification(
        id=11,
        user_id=1,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "recurring",
            "station_name": "강남",
            "line": "2호선",
            "repeat_interval_minutes": 10,
        },
    )
    user = _FakeUser(id=1, discord_id=9999)

    # 3분 전에 발송 → 10분 interval 미충족
    last_sent = _FIXED_NOW_UTC - timedelta(minutes=3)
    fake_client = _FakeSubwayClient([_make_arrival()], [])

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_ctx(queue=queue)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=last_sent),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: fake_client,
        )

        await run_transit_job(ctx)

    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# 케이스 3: KST now < start_time → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_FIXED_KST, tick=False)
async def test_recurring_before_window_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """현재 KST 시각이 start_time 이전 → skip."""
    notif = _FakeNotification(
        id=12,
        user_id=1,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "recurring",
            "station_name": "강남",
            "line": "2호선",
            "repeat_interval_minutes": 5,
            "start_time": "11:00:00",  # KST 현재(10:00) < 11:00 → skip
        },
    )
    user = _FakeUser(id=1, discord_id=9999)

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_ctx(queue=queue)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )

        await run_transit_job(ctx)

    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# 케이스 4: KST now > end_time → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_FIXED_KST, tick=False)
async def test_recurring_after_window_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """현재 KST 시각이 end_time 이후 → skip."""
    notif = _FakeNotification(
        id=13,
        user_id=1,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "recurring",
            "station_name": "강남",
            "line": "2호선",
            "repeat_interval_minutes": 5,
            "end_time": "09:00:00",  # KST 현재(10:00) > 09:00 → skip
        },
    )
    user = _FakeUser(id=1, discord_id=9999)

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_ctx(queue=queue)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )

        await run_transit_job(ctx)

    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# 케이스 5(원 케이스 6): 같은 station 다른 line 구독 2건 → fetch_arrivals 1회만 호출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_FIXED_KST, tick=False)
async def test_same_station_fetches_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """같은 역의 구독 2건 → SubwayClient.fetch_arrivals 호출 1회."""
    notif1 = _FakeNotification(
        id=20,
        user_id=1,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "recurring",
            "station_name": "강남",
            "line": "2호선",
            "repeat_interval_minutes": 0,
        },
    )
    notif2 = _FakeNotification(
        id=21,
        user_id=2,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "recurring",
            "station_name": "강남",
            "line": "9호선",
            "repeat_interval_minutes": 0,
        },
    )
    user1 = _FakeUser(id=1, discord_id=1111)
    user2 = _FakeUser(id=2, discord_id=2222)

    call_count: list[int] = []
    arrivals = [
        _make_arrival(direction="상행", seconds=60),
        SubwayArrival(
            station_name="강남",
            subway_id="1009",
            line_label="9호선",
            direction="상행",
            headed_for="개화",
            arrival_message="도착",
            arrival_message_detail="",
            arrival_seconds=90,
            train_no="9001",
            arvl_code=1,
            train_type="일반",
            train_line_name="",
            received_at=None,
        ),
    ]
    fake_client = _FakeSubwayClient(arrivals, call_count)

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_ctx(queue=queue)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif1, user1), (notif2, user2)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: fake_client,
        )

        await run_transit_job(ctx)

    # fetch_arrivals 는 딱 1회만 호출돼야 한다.
    assert len(call_count) == 1
    # 두 구독 모두 큐에 적재.
    assert queue.qsize() == 2


# ---------------------------------------------------------------------------
# 케이스 7: SubwayApiUnavailable → swallow + 큐 비어 있음
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_FIXED_KST, tick=False)
async def test_api_unavailable_swallowed_queue_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SubwayApiUnavailable 발생 → swallow, 큐 비어 있음."""
    notif = _FakeNotification(
        id=30,
        user_id=1,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "recurring",
            "station_name": "강남",
            "line": "2호선",
            "repeat_interval_minutes": 0,
        },
    )
    user = _FakeUser(id=1, discord_id=9999)

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_ctx(queue=queue)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: _RaisingSubwayClient(),
        )

        # 예외가 전파되지 않아야 한다 (swallow).
        await run_transit_job(ctx)

    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# 회귀 가드 1: repeat_interval_minutes 키 이름 — 30초 전 발송 + 5분 interval → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_FIXED_KST, tick=False)
async def test_regression_repeat_interval_minutes_key_is_respected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """repeat_interval_minutes 가드 동작 확인.

    마지막 발송이 30초 전이고 repeat_interval_minutes=5(300초)이면 skip.
    이 케이스가 fail 하면 config 키 이름 회귀('interval_minutes')가 재발한 것.
    """
    notif = _FakeNotification(
        id=40,
        user_id=1,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "recurring",
            "station_name": "강남",
            "line": "2호선",
            # 반드시 'repeat_interval_minutes' 키여야 가드가 활성화된다.
            "repeat_interval_minutes": 5,
        },
    )
    user = _FakeUser(id=1, discord_id=9999)

    # 30초 전에 발송 → 5분(300초) interval 미충족
    last_sent = _FIXED_NOW_UTC - timedelta(seconds=30)
    fake_client = _FakeSubwayClient([_make_arrival()], [])

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_ctx(queue=queue)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=last_sent),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: fake_client,
        )

        await run_transit_job(ctx)

    # 가드가 올바르게 동작하면 큐는 비어 있어야 한다.
    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# 회귀 가드 2: 타임존 비교가 KST 기준 — UTC 기준이면 윈도우 밖이지만 KST 기준이면 윈도우 안
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regression_window_comparison_uses_kst(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """윈도우 비교가 KST 기준임을 검증한다.

    KST 08:30 = UTC 전일 23:30. start=08:00, end=09:00(KST) 윈도우.
    UTC 기준이라면 23:30 은 08:00~09:00 밖이지만, KST 기준이면 안이므로 enqueue 돼야 한다.
    이 케이스가 fail 하면 UTC 기준 비교 회귀가 재발한 것.
    """
    # KST 2026-05-19 08:30:00 = UTC 2026-05-18 23:30:00
    frozen_kst = "2026-05-19T08:30:00+09:00"

    notif = _FakeNotification(
        id=50,
        user_id=1,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "recurring",
            "station_name": "강남",
            "line": "2호선",
            "repeat_interval_minutes": 0,
            "start_time": "08:00:00",  # KST 기준
            "end_time": "09:00:00",  # KST 기준
        },
    )
    user = _FakeUser(id=1, discord_id=9999)

    call_count: list[int] = []
    fake_client = _FakeSubwayClient([_make_arrival()], call_count)

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_ctx(queue=queue)

    with time_machine.travel(frozen_kst, tick=False):
        with monkeypatch.context() as m:
            m.setattr(
                "app.notifications.transit.worker.NotificationRepository",
                lambda session: _FakeNotificationRepo([(notif, user)]),
            )
            m.setattr(
                "app.notifications.transit.worker.NotificationHistoryRepository",
                lambda session: _FakeHistoryRepo(last_sent_at=None),
            )
            m.setattr(
                "app.notifications.transit.worker.SubwayClient",
                lambda http_client, settings, redis: fake_client,
            )

            await run_transit_job(ctx)

    # KST 08:30 은 08:00~09:00 윈도우 안이므로 큐에 적재돼야 한다.
    assert queue.qsize() == 1


# ===========================================================================
# run_immediate_send_transit_job 테스트
# ===========================================================================

# 즉시 발송용 fake row
_TRANSIT_ROW = ImmediateSendRequestRow(
    id=100,
    user_id=5,
    discord_id=55555,
    payload={"station_name": "강남", "line": "2호선"},
)


def _make_immediate_ctx(
    queue: asyncio.Queue[SendDmTask] | None = None,
    inflight: set[int] | None = None,
) -> JobContext:
    from pydantic import SecretStr

    settings = MagicMock()
    settings.subway_api_key = SecretStr("test-key")

    return JobContext(
        queue=queue or asyncio.Queue(),
        http_client=httpx.AsyncClient(),
        session_maker=MagicMock(),
        settings=settings,
        redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True),
        in_flight_notification_ids=set(),
        immediate_send_inflight=inflight if inflight is not None else set(),
    )


class _FakeImmediateTransitRepo:
    """list_pending 이 고정 rows 를 반환하는 stub."""

    def __init__(self, rows: list[ImmediateSendRequestRow]) -> None:
        self._rows = rows

    async def list_pending(self, limit: int = 50) -> list[ImmediateSendRequestRow]:
        return self._rows


class _FakeImmediateHistoryRepo:
    """insert_result 호출을 기록하는 spy."""

    def __init__(self) -> None:
        self.inserts: list[dict[str, Any]] = []

    async def insert_result(self, **kwargs: Any) -> None:
        self.inserts.append(kwargs)

    async def get_last_sent_at(self, *args: Any, **kwargs: Any) -> None:
        return None


class _FakeImmediateSession:
    def __init__(
        self,
        transit_repo: _FakeImmediateTransitRepo,
        history_repo: _FakeImmediateHistoryRepo,
    ) -> None:
        self._transit_repo = transit_repo
        self._history_repo = history_repo
        self.committed = False

    async def __aenter__(self) -> "_FakeImmediateSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True


# ---------------------------------------------------------------------------
# 케이스 1 (즉시): happy path — 큐 1건 적재
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_immediate_transit_happy_path_enqueues_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """payload row 1건 → SubwayClient 호출 → 큐 1건 적재 + inflight 에 row.id 존재."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_immediate_ctx(queue=queue)

    transit_repo = _FakeImmediateTransitRepo([_TRANSIT_ROW])
    history_repo = _FakeImmediateHistoryRepo()
    fake_session = _FakeImmediateSession(transit_repo, history_repo)

    monkeypatch.setattr(
        "app.notifications.transit.worker.ImmediateSendTransitRepository",
        lambda session: transit_repo,
    )
    monkeypatch.setattr(
        "app.notifications.transit.worker.NotificationHistoryRepository",
        lambda session: history_repo,
    )
    monkeypatch.setattr(
        "app.notifications.transit.worker.SubwayClient",
        lambda http_client, settings, redis: _FakeSubwayClient([_make_arrival()], []),
    )
    ctx.session_maker.return_value.__aenter__.return_value = fake_session  # type: ignore[attr-defined]
    ctx.session_maker.return_value.__aexit__.return_value = False  # type: ignore[attr-defined]

    await run_immediate_send_transit_job(ctx)

    assert queue.qsize() == 1
    task = await queue.get()
    assert task.immediate_send_request_id == _TRANSIT_ROW.id
    assert task.notification_id is None
    assert task.user_id == _TRANSIT_ROW.user_id
    assert task.discord_id == _TRANSIT_ROW.discord_id
    assert _TRANSIT_ROW.id in ctx.immediate_send_inflight


# ---------------------------------------------------------------------------
# 케이스 2 (즉시): in-flight 스킵
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_immediate_transit_skips_inflight_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ctx.immediate_send_inflight 에 미리 추가된 row 는 fetch_arrivals 없이 skip."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_immediate_ctx(queue=queue, inflight={_TRANSIT_ROW.id})

    transit_repo = _FakeImmediateTransitRepo([_TRANSIT_ROW])
    history_repo = _FakeImmediateHistoryRepo()
    fake_session = _FakeImmediateSession(transit_repo, history_repo)

    fetch_count: list[int] = []

    class _CountingClient:
        async def fetch_arrivals(self, station_name: str) -> list[SubwayArrival]:
            fetch_count.append(1)
            return [_make_arrival()]

    monkeypatch.setattr(
        "app.notifications.transit.worker.ImmediateSendTransitRepository",
        lambda session: transit_repo,
    )
    monkeypatch.setattr(
        "app.notifications.transit.worker.NotificationHistoryRepository",
        lambda session: history_repo,
    )
    monkeypatch.setattr(
        "app.notifications.transit.worker.SubwayClient",
        lambda http_client, settings, redis: _CountingClient(),
    )
    ctx.session_maker.return_value.__aenter__.return_value = fake_session  # type: ignore[attr-defined]
    ctx.session_maker.return_value.__aexit__.return_value = False  # type: ignore[attr-defined]

    await run_immediate_send_transit_job(ctx)

    assert len(fetch_count) == 0, (
        "in-flight row 에 대해 fetch_arrivals 호출되어선 안 된다"
    )
    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# 케이스 3 (즉시): SubwayApiUnavailable → FAILED history INSERT + discard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_immediate_transit_api_unavailable_inserts_failed_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SubwayApiUnavailable 시 FAILED history row 1건 + inflight 에서 discard."""
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_immediate_ctx(queue=queue)

    transit_repo = _FakeImmediateTransitRepo([_TRANSIT_ROW])
    history_repo = _FakeImmediateHistoryRepo()
    fake_session = _FakeImmediateSession(transit_repo, history_repo)

    monkeypatch.setattr(
        "app.notifications.transit.worker.ImmediateSendTransitRepository",
        lambda session: transit_repo,
    )
    monkeypatch.setattr(
        "app.notifications.transit.worker.NotificationHistoryRepository",
        lambda session: history_repo,
    )
    monkeypatch.setattr(
        "app.notifications.transit.worker.SubwayClient",
        lambda http_client, settings, redis: _RaisingSubwayClient(),
    )
    ctx.session_maker.return_value.__aenter__.return_value = fake_session  # type: ignore[attr-defined]
    ctx.session_maker.return_value.__aexit__.return_value = False  # type: ignore[attr-defined]

    await run_immediate_send_transit_job(ctx)

    assert queue.qsize() == 0
    assert len(history_repo.inserts) == 1
    insert = history_repo.inserts[0]
    assert insert["immediate_send_request_id"] == _TRANSIT_ROW.id
    assert insert["status"] == NotificationDeliveryStatus.FAILED
    assert insert["failure_reason"] is not None
    # FAILED 후 inflight 에서 제거되어야 한다.
    assert _TRANSIT_ROW.id not in ctx.immediate_send_inflight


# ---------------------------------------------------------------------------
# 케이스 4 (즉시): DELETED 사용자 필터 — list_pending 에서 제외됨 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_immediate_transit_deleted_user_excluded_at_list_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETED 사용자 row 가 list_pending 에서 반환되지 않으면 큐에 적재되지 않는다.

    실제 DB 없이: list_pending 이 빈 목록을 반환하도록 monkeypatch.
    ImmediateSendTransitRepository 의 WHERE User.status == ACTIVE 필터에 의해
    DELETED 사용자 row 가 쿼리 단계에서 제외된 상황을 시뮬레이션한다.
    """
    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_immediate_ctx(queue=queue)

    # DELETED 사용자의 row 는 list_pending 이 비어 있는 결과로 돌아온다.
    transit_repo = _FakeImmediateTransitRepo([])
    history_repo = _FakeImmediateHistoryRepo()
    fake_session = _FakeImmediateSession(transit_repo, history_repo)

    fetch_count: list[int] = []

    class _CountingClient:
        async def fetch_arrivals(self, station_name: str) -> list[SubwayArrival]:
            fetch_count.append(1)
            return [_make_arrival()]

    monkeypatch.setattr(
        "app.notifications.transit.worker.ImmediateSendTransitRepository",
        lambda session: transit_repo,
    )
    monkeypatch.setattr(
        "app.notifications.transit.worker.NotificationHistoryRepository",
        lambda session: history_repo,
    )
    monkeypatch.setattr(
        "app.notifications.transit.worker.SubwayClient",
        lambda http_client, settings, redis: _CountingClient(),
    )
    ctx.session_maker.return_value.__aenter__.return_value = fake_session  # type: ignore[attr-defined]
    ctx.session_maker.return_value.__aexit__.return_value = False  # type: ignore[attr-defined]

    await run_immediate_send_transit_job(ctx)

    assert queue.qsize() == 0
    assert len(fetch_count) == 0, (
        "DELETED 사용자 row 는 fetch_arrivals 가 호출되어선 안 된다"
    )
    assert len(history_repo.inserts) == 0


# ===========================================================================
# F-06 arrival 모드 테스트 (fakeredis 사용)
# ===========================================================================

# KST 2026-05-20 10:00:00 = UTC 2026-05-20 01:00:00
_ARRIVAL_FIXED_KST = "2026-05-20T10:00:00+09:00"
_ARRIVAL_FIXED_NOW_UTC = datetime(2026, 5, 20, 1, 0, 0, tzinfo=timezone.utc)
_ARRIVAL_KST_DATE = "2026-05-20"

_ARRIVAL_NOTIF_CFG: dict[str, Any] = {
    "mode": "arrival",
    "station_name": "강남",
    "line": "2호선",
    "direction": "상행",
    "start_time": "09:00:00",
    "end_time": "11:00:00",
    "minutes_before": 5,
}


def _make_arrival_ctx(
    queue: asyncio.Queue[SendDmTask] | None = None,
    redis: Any = None,
) -> JobContext:
    from pydantic import SecretStr

    settings = MagicMock()
    settings.subway_api_key = SecretStr("test-key")

    return JobContext(
        queue=queue or asyncio.Queue(),
        http_client=httpx.AsyncClient(),
        session_maker=_FakeSessionMaker(),  # type: ignore[arg-type]
        settings=settings,
        in_flight_notification_ids=set(),
        redis_client=redis,
    )


# ---------------------------------------------------------------------------
# arrival 케이스 1: happy path — train_no 2개 매칭 → 큐 2건 + Redis SET 에 2개
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_ARRIVAL_FIXED_KST, tick=False)
async def test_arrival_happy_path_enqueues_two_trains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """윈도우 내, 상행 2호선 열차 2대 매칭 → 큐 2건 + Redis SET 에 train_no 2개."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    notif = _FakeNotification(
        id=200,
        user_id=10,
        type=NotificationType.TRANSIT,
        enabled=True,
        config=_ARRIVAL_NOTIF_CFG,
    )
    user = _FakeUser(id=10, discord_id=88888)

    arrivals = [
        _make_arrival(direction="상행", seconds=200, train_no="A001"),
        _make_arrival(direction="상행", seconds=250, train_no="A002"),
        _make_arrival(direction="하행", seconds=180, train_no="B001"),  # 방향 미스매치
    ]

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_arrival_ctx(queue=queue, redis=redis)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: _FakeSubwayClient(arrivals, []),
        )

        await run_transit_job(ctx)

    assert queue.qsize() == 2

    redis_key = _ARRIVAL_REDIS_KEY_TEMPLATE.format(
        notification_id=200, kst_date=_ARRIVAL_KST_DATE
    )
    members = await redis.smembers(redis_key)
    assert members == {"A001", "A002"}


# ---------------------------------------------------------------------------
# arrival 케이스 2: train_no 이미 sent → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_ARRIVAL_FIXED_KST, tick=False)
async def test_arrival_already_sent_train_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis SET 에 이미 존재하는 train_no → 해당 arrival skip, 큐 0건."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_key = _ARRIVAL_REDIS_KEY_TEMPLATE.format(
        notification_id=201, kst_date=_ARRIVAL_KST_DATE
    )
    await redis.sadd(redis_key, "A001")

    notif = _FakeNotification(
        id=201,
        user_id=11,
        type=NotificationType.TRANSIT,
        enabled=True,
        config=_ARRIVAL_NOTIF_CFG,
    )
    user = _FakeUser(id=11, discord_id=77777)
    arrivals = [_make_arrival(direction="상행", seconds=200, train_no="A001")]

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_arrival_ctx(queue=queue, redis=redis)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: _FakeSubwayClient(arrivals, []),
        )

        await run_transit_job(ctx)

    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# arrival 케이스 3: 윈도우 밖 skip (now_kst < start_time)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_arrival_before_window_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """KST 08:00 — start_time=09:00 → 윈도우 밖 → 큐 0건, Redis 호출 없음."""
    # KST 08:00 = UTC 전일 23:00
    frozen_kst = "2026-05-20T08:00:00+09:00"
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    notif = _FakeNotification(
        id=202,
        user_id=12,
        type=NotificationType.TRANSIT,
        enabled=True,
        config=_ARRIVAL_NOTIF_CFG,  # start_time=09:00
    )
    user = _FakeUser(id=12, discord_id=66666)
    arrivals = [_make_arrival(direction="상행", seconds=200, train_no="A001")]
    call_count: list[int] = []

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_arrival_ctx(queue=queue, redis=redis)

    with time_machine.travel(frozen_kst, tick=False):
        with monkeypatch.context() as m:
            m.setattr(
                "app.notifications.transit.worker.NotificationRepository",
                lambda session: _FakeNotificationRepo([(notif, user)]),
            )
            m.setattr(
                "app.notifications.transit.worker.NotificationHistoryRepository",
                lambda session: _FakeHistoryRepo(last_sent_at=None),
            )
            m.setattr(
                "app.notifications.transit.worker.SubwayClient",
                lambda http_client, settings, redis: _FakeSubwayClient(
                    arrivals, call_count
                ),
            )

            await run_transit_job(ctx)

    assert queue.qsize() == 0
    # 윈도우 밖이므로 SubwayClient 호출 없어야 함 (Redis 키 검사 전 skip).
    assert len(call_count) == 0


# ---------------------------------------------------------------------------
# arrival 케이스 4: direction 미스매치 skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_ARRIVAL_FIXED_KST, tick=False)
async def test_arrival_direction_mismatch_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cfg.direction='상행' 인데 arrival.direction='하행' → skip, 큐 0건."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    notif = _FakeNotification(
        id=203,
        user_id=13,
        type=NotificationType.TRANSIT,
        enabled=True,
        config=_ARRIVAL_NOTIF_CFG,  # direction=상행
    )
    user = _FakeUser(id=13, discord_id=55555)
    arrivals = [_make_arrival(direction="하행", seconds=200, train_no="B001")]

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_arrival_ctx(queue=queue, redis=redis)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: _FakeSubwayClient(arrivals, []),
        )

        await run_transit_job(ctx)

    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# arrival 케이스 5: effective_seconds > minutes_before*60 → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_ARRIVAL_FIXED_KST, tick=False)
async def test_arrival_too_far_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """arrival_seconds=600 (10분) > minutes_before=5분(300초) → skip."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    notif = _FakeNotification(
        id=204,
        user_id=14,
        type=NotificationType.TRANSIT,
        enabled=True,
        config=_ARRIVAL_NOTIF_CFG,  # minutes_before=5
    )
    user = _FakeUser(id=14, discord_id=44444)
    arrivals = [
        _make_arrival(direction="상행", seconds=600, train_no="A001")  # 10분
    ]

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_arrival_ctx(queue=queue, redis=redis)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: _FakeSubwayClient(arrivals, []),
        )

        await run_transit_job(ctx)

    assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# arrival 케이스 6: TTL NX 동작 — 두 번째 SADD 시 TTL 초기화 안 됨
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_ARRIVAL_FIXED_KST, tick=False)
async def test_arrival_ttl_nx_not_reset_on_second_sadd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """같은 키에 두 번째 열차 SADD 시 EXPIRE NX → TTL 이 초기화되지 않는다.

    첫 번째 SADD 후 TTL 을 임의로 설정한 뒤 두 번째 열차를 적재.
    expire NX 이므로 TTL 이 이미 있으면 덮어 쓰지 않는다.
    """
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    redis_key = _ARRIVAL_REDIS_KEY_TEMPLATE.format(
        notification_id=206, kst_date=_ARRIVAL_KST_DATE
    )
    # 먼저 키에 짧은 TTL(100s) 설정 — 이미 발송된 이력이 있는 상황 시뮬레이션.
    await redis.sadd(redis_key, "EXISTING")
    await redis.expire(redis_key, 100)

    notif = _FakeNotification(
        id=206,
        user_id=16,
        type=NotificationType.TRANSIT,
        enabled=True,
        config=_ARRIVAL_NOTIF_CFG,
    )
    user = _FakeUser(id=16, discord_id=22222)
    arrivals = [_make_arrival(direction="상행", seconds=200, train_no="A_NEW")]

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
    ctx = _make_arrival_ctx(queue=queue, redis=redis)

    with monkeypatch.context() as m:
        m.setattr(
            "app.notifications.transit.worker.NotificationRepository",
            lambda session: _FakeNotificationRepo([(notif, user)]),
        )
        m.setattr(
            "app.notifications.transit.worker.NotificationHistoryRepository",
            lambda session: _FakeHistoryRepo(last_sent_at=None),
        )
        m.setattr(
            "app.notifications.transit.worker.SubwayClient",
            lambda http_client, settings, redis: _FakeSubwayClient(arrivals, []),
        )

        await run_transit_job(ctx)

    assert queue.qsize() == 1

    ttl = await redis.ttl(redis_key)
    # EXPIRE NX 이므로 기존 100s TTL 이 유지돼야 한다 (28h=100800s 로 덮어 쓰면 안 됨).
    assert ttl <= 100, f"TTL 이 NX 무시하고 리셋됨: {ttl}"
    assert ttl > 0, "TTL 이 만료돼서는 안 됨"
