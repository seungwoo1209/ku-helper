"""Sender 큐 워커 통합 테스트 (§A-2).

실제 DB 없이 fake session / spy repository 로 검증한다.
회귀 가드 3종:
  1. DELETED 사용자 — dc_channel.send 호출 0회 + FAILED history INSERT.
  2. discord.HTTPException 발생 — FAILED history INSERT + 큐 비워짐.
  3. 정상 발송 — SUCCESS history INSERT.
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from app.db.models import NotificationDeliveryStatus, UserStatus
from app.notifications.sender import SendDmTask, run_sender_worker


# ---------------------------------------------------------------------------
# 헬퍼 / 스파이
# ---------------------------------------------------------------------------


@dataclass
class _InsertCall:
    notification_id: int | None
    user_id: int
    status: NotificationDeliveryStatus
    payload: dict[str, Any]
    failure_reason: str | None
    immediate_send_request_id: int | None = None


class _FakeHistoryRepo:
    def __init__(self) -> None:
        self.calls: list[_InsertCall] = []

    async def insert_result(
        self,
        *,
        notification_id: int | None,
        user_id: int,
        status: NotificationDeliveryStatus,
        payload: dict[str, Any],
        failure_reason: str | None = None,
        immediate_send_request_id: int | None = None,
    ) -> None:
        self.calls.append(
            _InsertCall(
                notification_id=notification_id,
                user_id=user_id,
                status=status,
                payload=payload,
                failure_reason=failure_reason,
                immediate_send_request_id=immediate_send_request_id,
            )
        )


class _FakeNotificationRepo:
    def __init__(self, user_status: UserStatus | None) -> None:
        self._status = user_status

    async def get_user_status(self, user_id: int) -> UserStatus | None:
        return self._status


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def dc_channel() -> AsyncMock:
    ch = AsyncMock(spec=discord.DMChannel)
    return ch


@pytest.fixture
def discord_client(dc_channel: AsyncMock) -> Any:
    dc_user = AsyncMock(spec=discord.User)
    dc_user.create_dm.return_value = dc_channel

    raw = MagicMock(spec=discord.Client)
    raw.fetch_user = AsyncMock(return_value=dc_user)
    raw.wait_until_ready = AsyncMock()

    from app.core.discord import DiscordBotClient

    settings = MagicMock()
    return DiscordBotClient(raw, settings)


def _make_task(user_id: int = 1, discord_id: int = 9999) -> SendDmTask:
    return SendDmTask(
        notification_id=42,
        user_id=user_id,
        discord_id=discord_id,
        embed=discord.Embed(title="테스트"),
        payload={"type": "TRANSIT"},
    )


# ---------------------------------------------------------------------------
# 유틸: 워커 실행 헬퍼
# ---------------------------------------------------------------------------


async def _run_worker_with_task(
    task: SendDmTask,
    discord_client: Any,
    user_status: UserStatus | None,
) -> tuple[_FakeHistoryRepo, AsyncMock]:
    """task 1개를 큐에 넣어 워커가 처리하도록 하고, fake repo 와 dc_channel 을 반환한다."""
    history_repo = _FakeHistoryRepo()
    notification_repo = _FakeNotificationRepo(user_status)

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

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()

    with (
        patch(
            "app.notifications.sender.NotificationHistoryRepository",
            return_value=history_repo,
        ),
        patch(
            "app.notifications.sender.NotificationRepository",
            return_value=notification_repo,
        ),
    ):
        worker = asyncio.create_task(
            run_sender_worker(
                queue,
                discord_client,
                _FakeSessionMaker(),  # type: ignore[arg-type]
                in_flight_notification_ids=set(),
            )
        )
        await queue.put(task)
        await queue.join()
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    return history_repo, discord_client._client.fetch_user


# ---------------------------------------------------------------------------
# 회귀 가드 1: DELETED 사용자
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deleted_user_no_dm_sent_and_failed_history(
    discord_client: Any,
    dc_channel: AsyncMock,
) -> None:
    """DELETED 사용자에게는 DM 이 발송되지 않고 FAILED history 가 INSERT 되어야 한다."""
    task = _make_task()
    history_repo, _ = await _run_worker_with_task(
        task, discord_client, UserStatus.DELETED
    )

    # DM 발송 금지
    dc_channel.send.assert_not_awaited()

    # FAILED history 1 row
    assert len(history_repo.calls) == 1
    call = history_repo.calls[0]
    assert call.status == NotificationDeliveryStatus.FAILED
    assert call.failure_reason == "user_deleted"
    assert call.user_id == task.user_id


@pytest.mark.asyncio
async def test_nonexistent_user_no_dm_sent_and_failed_history(
    discord_client: Any,
    dc_channel: AsyncMock,
) -> None:
    """사용자 행이 없으면(None) DM 이 발송되지 않고 FAILED 로 기록되어야 한다."""
    task = _make_task()
    history_repo, _ = await _run_worker_with_task(
        task, discord_client, user_status=None
    )

    dc_channel.send.assert_not_awaited()
    assert len(history_repo.calls) == 1
    assert history_repo.calls[0].status == NotificationDeliveryStatus.FAILED
    assert history_repo.calls[0].failure_reason == "user_deleted"


# ---------------------------------------------------------------------------
# 회귀 가드 2: discord.HTTPException 발생
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_exception_results_in_failed_history(
    discord_client: Any,
    dc_channel: AsyncMock,
) -> None:
    """discord.HTTPException 발생 시 FAILED history 1 row + 큐가 비워져야 한다."""
    dc_channel.send.side_effect = discord.HTTPException(
        MagicMock(status=500), "Internal Server Error"
    )
    task = _make_task()
    history_repo, _ = await _run_worker_with_task(
        task, discord_client, UserStatus.ACTIVE
    )

    assert len(history_repo.calls) == 1
    call = history_repo.calls[0]
    assert call.status == NotificationDeliveryStatus.FAILED
    assert call.failure_reason is not None
    assert "Internal Server Error" in call.failure_reason


# ---------------------------------------------------------------------------
# 회귀 가드 3: 정상 발송
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_send_inserts_success_history(
    discord_client: Any,
    dc_channel: AsyncMock,
) -> None:
    """정상 발송 시 SUCCESS history 1 row 가 INSERT 되어야 한다."""
    task = _make_task()
    history_repo, _ = await _run_worker_with_task(
        task, discord_client, UserStatus.ACTIVE
    )

    dc_channel.send.assert_awaited_once()
    assert len(history_repo.calls) == 1
    assert history_repo.calls[0].status == NotificationDeliveryStatus.SUCCESS
    assert history_repo.calls[0].user_id == task.user_id
    assert history_repo.calls[0].notification_id == task.notification_id


# ---------------------------------------------------------------------------
# NotificationHistoryRepository INSERT 시그니처 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_flight_set_discarded_after_processing(
    discord_client: Any,
    dc_channel: AsyncMock,
) -> None:
    """notification_id 가 in_flight set 에 있는 상태로 task 처리 → 처리 후 set 에서 제거."""
    task = _make_task()
    history_repo = _FakeHistoryRepo()
    notification_repo = _FakeNotificationRepo(UserStatus.ACTIVE)
    in_flight: set[int] = {task.notification_id}  # type: ignore[arg-type]

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

    queue: asyncio.Queue[SendDmTask] = asyncio.Queue()

    with (
        patch(
            "app.notifications.sender.NotificationHistoryRepository",
            return_value=history_repo,
        ),
        patch(
            "app.notifications.sender.NotificationRepository",
            return_value=notification_repo,
        ),
    ):
        worker = asyncio.create_task(
            run_sender_worker(
                queue,
                discord_client,
                _FakeSessionMaker(),  # type: ignore[arg-type]
                in_flight_notification_ids=in_flight,
            )
        )
        await queue.put(task)
        await queue.join()
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    # 처리 완료 후 in_flight 에서 제거돼야 한다.
    assert task.notification_id not in in_flight


@pytest.mark.asyncio
async def test_history_repository_insert_result_sets_all_fields() -> None:
    """insert_result 가 모든 필드를 올바르게 NotificationHistory 에 add 하는지 검증."""
    from unittest.mock import AsyncMock as _AM, MagicMock as _MM
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.notifications.history_repository import NotificationHistoryRepository
    from app.db.models import NotificationHistory

    session = _MM(spec=AsyncSession)
    session.add = _MM()
    session.flush = _AM()

    repo = NotificationHistoryRepository(session)
    await repo.insert_result(
        notification_id=7,
        user_id=3,
        status=NotificationDeliveryStatus.SUCCESS,
        payload={"k": "v"},
        failure_reason=None,
    )

    session.add.assert_called_once()
    row: NotificationHistory = session.add.call_args[0][0]
    assert row.notification_id == 7
    assert row.user_id == 3
    assert row.status == NotificationDeliveryStatus.SUCCESS
    assert row.payload == {"k": "v"}
    assert row.failure_reason is None
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_history_repository_insert_result_with_failure_reason() -> None:
    from unittest.mock import AsyncMock as _AM, MagicMock as _MM
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.notifications.history_repository import NotificationHistoryRepository
    from app.db.models import NotificationHistory

    session = _MM(spec=AsyncSession)
    session.add = _MM()
    session.flush = _AM()

    repo = NotificationHistoryRepository(session)
    await repo.insert_result(
        notification_id=None,
        user_id=5,
        status=NotificationDeliveryStatus.FAILED,
        payload={},
        failure_reason="user_deleted",
    )

    row: NotificationHistory = session.add.call_args[0][0]
    assert row.notification_id is None
    assert row.failure_reason == "user_deleted"
    assert row.status == NotificationDeliveryStatus.FAILED


# ---------------------------------------------------------------------------
# §A-3 회귀 가드: 지수 백오프 재시도
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_failures_insert_failed_history_once(
    discord_client: Any,
    dc_channel: AsyncMock,
) -> None:
    """3회 모두 discord.HTTPException → FAILED history 1 row, send 호출 3회."""
    dc_channel.send.side_effect = discord.HTTPException(
        MagicMock(status=500), "server error"
    )
    task = _make_task()

    with patch("app.notifications.sender.asyncio.sleep", new_callable=AsyncMock):
        history_repo, _ = await _run_worker_with_task(
            task, discord_client, UserStatus.ACTIVE
        )

    # history INSERT 정확히 1회
    assert len(history_repo.calls) == 1
    call = history_repo.calls[0]
    assert call.status == NotificationDeliveryStatus.FAILED
    assert call.failure_reason is not None
    assert "server error" in call.failure_reason

    # send 3회 호출
    assert dc_channel.send.await_count == 3


@pytest.mark.asyncio
async def test_two_failures_then_success_inserts_success_history_once(
    discord_client: Any,
    dc_channel: AsyncMock,
) -> None:
    """2회 실패 후 3번째 성공 → SUCCESS history 1 row, send 3회 호출."""
    exc = discord.HTTPException(MagicMock(status=500), "temporary error")
    dc_channel.send.side_effect = [exc, exc, None]
    task = _make_task()

    with patch("app.notifications.sender.asyncio.sleep", new_callable=AsyncMock):
        history_repo, _ = await _run_worker_with_task(
            task, discord_client, UserStatus.ACTIVE
        )

    assert len(history_repo.calls) == 1
    assert history_repo.calls[0].status == NotificationDeliveryStatus.SUCCESS
    assert dc_channel.send.await_count == 3


@pytest.mark.asyncio
async def test_first_attempt_success_no_sleep(
    discord_client: Any,
    dc_channel: AsyncMock,
) -> None:
    """1회 성공 시 sleep 호출 0회, SUCCESS history 1 row."""
    task = _make_task()

    with patch(
        "app.notifications.sender.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        history_repo, _ = await _run_worker_with_task(
            task, discord_client, UserStatus.ACTIVE
        )

    mock_sleep.assert_not_awaited()
    assert len(history_repo.calls) == 1
    assert history_repo.calls[0].status == NotificationDeliveryStatus.SUCCESS


@pytest.mark.asyncio
async def test_backoff_sleep_arguments(
    discord_client: Any,
    dc_channel: AsyncMock,
) -> None:
    """백오프 sleep 인자 검증: 첫 sleep 1.0초, 두 번째 sleep 2.0초."""
    exc = discord.HTTPException(MagicMock(status=500), "fail")
    # 3회 모두 실패시켜 sleep 2회(1.0, 2.0)가 호출되게 한다.
    dc_channel.send.side_effect = exc

    task = _make_task()
    sleep_calls: list[float] = []

    async def _capture_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    with patch("app.notifications.sender.asyncio.sleep", side_effect=_capture_sleep):
        await _run_worker_with_task(task, discord_client, UserStatus.ACTIVE)

    assert sleep_calls == [1.0, 2.0]
