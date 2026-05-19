"""run_transit_job 단위 테스트 (F-07 recurring 모드).

time-machine 으로 시각 고정, fake SubwayClient/Repository 를 monkeypatch 로 주입.
APScheduler 를 거치지 않고 run_transit_job(ctx) 를 직접 await 한다.

시각 고정 규칙:
- freeze 시각은 KST 오프셋(+09:00)을 명시한 ISO 문자열 사용.
- KST 08:00 = UTC 23:00 전일. 윈도우 비교가 KST 기준인지 검증할 때 이 차이를 이용한다.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import time_machine

from app.crawlers.subway.client import SubwayArrival
from app.crawlers.subway.exceptions import SubwayApiUnavailable
from app.db.models import NotificationDeliveryStatus, NotificationType
from app.notifications.sender import SendDmTask
from app.notifications.transit.worker import run_transit_job
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


def _make_arrival(direction: str = "상행", seconds: int = 120) -> SubwayArrival:
    return SubwayArrival(
        station_name="강남",
        subway_id="1002",
        line_label="2호선",
        direction=direction,
        headed_for="성수",
        arrival_message="도착",
        arrival_message_detail="강남 도착",
        arrival_seconds=seconds,
        train_no="2001",
        arvl_code=1,
        train_type="일반",
    )


def _make_ctx(
    queue: asyncio.Queue[SendDmTask] | None = None,
    in_flight: set[int] | None = None,
) -> JobContext:
    from pydantic import SecretStr

    settings = MagicMock()
    settings.subway_api_key = SecretStr("test-key")

    return JobContext(
        queue=queue or asyncio.Queue(),
        http_client=httpx.AsyncClient(),
        session_maker=_FakeSessionMaker(),  # type: ignore[arg-type]
        settings=settings,
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
            lambda http_client, settings: fake_client,
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
            lambda http_client, settings: fake_client,
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
# 케이스 5: mode == "arrival" → skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@time_machine.travel(_FIXED_KST, tick=False)
async def test_arrival_mode_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """mode == 'arrival' → skip (F-06 후속 PR)."""
    notif = _FakeNotification(
        id=14,
        user_id=1,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={
            "mode": "arrival",
            "station_name": "강남",
            "line": "2호선",
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
# 케이스 6: 같은 station 다른 line 구독 2건 → fetch_arrivals 1회만 호출
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
            lambda http_client, settings: fake_client,
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
            lambda http_client, settings: _RaisingSubwayClient(),
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
            lambda http_client, settings: fake_client,
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
                lambda http_client, settings: fake_client,
            )

            await run_transit_job(ctx)

    # KST 08:30 은 08:00~09:00 윈도우 안이므로 큐에 적재돼야 한다.
    assert queue.qsize() == 1
