"""Sender 큐 워커.

asyncio.Queue[SendDmTask] 1개 + 워커 코루틴 1개.
Discord API rate limit 준수를 위해 워커는 단일 인스턴스만 유지한다 (architecture.md Sender 절).

§A-3 지수 백오프 재시도는 다음 PR. 본 PR 에서는 발송 실패 시 FAILED 1행 INSERT 후 종료.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import discord
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.discord import DiscordBotClient
from app.db.models import NotificationDeliveryStatus, UserStatus
from app.notifications.history_repository import NotificationHistoryRepository
from app.notifications.repository import NotificationRepository

_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SendDmTask:
    """Sender 큐에 적재되는 발송 작업.

    notification_id 가 None 인 경우는 관리자 알림(F-22) 등 알림 행이 없는 케이스.
    embed 는 discord.Embed(가변 객체)이므로 compare=False 로 처리해
    frozen=True 의 hash 충돌을 방지한다.
    payload 는 notification_history.payload JSONB 로 저장되는 임베드 스냅샷 dict.
    """

    notification_id: int | None
    user_id: int
    discord_id: int
    embed: discord.Embed = field(compare=False)
    payload: dict[str, Any]


async def run_sender_worker(
    queue: asyncio.Queue[SendDmTask],
    discord_client: DiscordBotClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Sender 큐를 소비하는 워커 코루틴.

    lifespan 에서 asyncio.create_task 로 띄운다.
    discord.Client 가 ready 상태가 될 때까지 대기한 뒤 루프 진입.

    CancelledError 는 lifespan 종료 신호이므로 swallow 하지 않고 전파.
    그 외 예외는 워커가 죽지 않도록 catch 해 로깅 + FAILED INSERT 후 계속.
    """
    # discord.Client 가 ready 될 때까지 대기.
    await discord_client.wait_until_ready()

    while True:
        task = await queue.get()
        try:
            await _process_task(task, discord_client, session_maker)
        except asyncio.CancelledError:
            queue.task_done()
            raise
        except Exception:
            # 워커 자체를 살려 두기 위해 예외를 삼킨다.
            # _process_task 내부에서 이미 FAILED INSERT 했지만,
            # 예상치 못한 예외가 _process_task 밖으로 나왔을 때의 안전망.
            _logger.exception("sender_worker_unexpected", user_id=task.user_id)
        finally:
            queue.task_done()


async def _process_task(
    task: SendDmTask,
    discord_client: DiscordBotClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """SendDmTask 1건을 처리한다. 1 task = 1 트랜잭션 = 1 commit."""
    async with session_maker() as session:
        history_repo = NotificationHistoryRepository(session)
        notification_repo = NotificationRepository(session)

        # 이중 가드: 큐에서 꺼낸 시점에 사용자 상태 재검증.
        user_status = await notification_repo.get_user_status(task.user_id)
        if user_status != UserStatus.ACTIVE:
            _logger.info(
                "sender_skip_inactive_user",
                user_id=task.user_id,
                status=str(user_status),
            )
            await history_repo.insert_result(
                notification_id=task.notification_id,
                user_id=task.user_id,
                status=NotificationDeliveryStatus.FAILED,
                payload=task.payload,
                failure_reason="user_deleted",
            )
            await session.commit()
            return

        try:
            await discord_client.send_embed(task.discord_id, task.embed)
        except discord.DiscordException as exc:
            _logger.warning(
                "sender_discord_error",
                user_id=task.user_id,
                discord_id=task.discord_id,
                error=str(exc)[:200],
            )
            await history_repo.insert_result(
                notification_id=task.notification_id,
                user_id=task.user_id,
                status=NotificationDeliveryStatus.FAILED,
                payload=task.payload,
                failure_reason=str(exc)[:200],
            )
            await session.commit()
            return
        except Exception:
            _logger.exception(
                "sender_worker_unexpected",
                user_id=task.user_id,
                discord_id=task.discord_id,
            )
            await history_repo.insert_result(
                notification_id=task.notification_id,
                user_id=task.user_id,
                status=NotificationDeliveryStatus.FAILED,
                payload=task.payload,
                failure_reason="unexpected_error",
            )
            await session.commit()
            return

        await history_repo.insert_result(
            notification_id=task.notification_id,
            user_id=task.user_id,
            status=NotificationDeliveryStatus.SUCCESS,
            payload=task.payload,
        )
        await session.commit()
        _logger.info(
            "dm_sent",
            user_id=task.user_id,
            discord_id=task.discord_id,
            notification_id=task.notification_id,
        )
