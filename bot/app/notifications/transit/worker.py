"""TRANSIT 알림 워커 — F-07 정기 간격(recurring) 모드.

Scheduler → Worker → (SubwayClient · Repository) → Sender 순서를 따른다.
F-18 활성 시간대·Redis 캐시는 후속 PR 에서 추가한다.
"""

from datetime import datetime, timezone

import structlog

from app.crawlers.subway.client import SubwayClient
from app.crawlers.subway.exceptions import SubwayApiUnavailable
from app.core.exceptions import BotException
from app.db.models import NotificationDeliveryStatus, NotificationType
from app.notifications.history_repository import NotificationHistoryRepository
from app.notifications.repository import NotificationRepository
from app.notifications.sender import SendDmTask
from app.notifications.transit.embeds import build_transit_recurring_embed
from app.scheduler.context import JobContext

_logger = structlog.get_logger(__name__)


async def run_transit_job(ctx: JobContext) -> None:
    """TRANSIT 활성 구독을 폴링하여 F-07 조건 충족 시 Sender 큐에 적재한다.

    - mode == "recurring" 만 처리. "arrival" 은 skip(F-06 후속 PR).
    - 같은 역(station) 구독이 여러 개이면 fetch_arrivals 는 한 번만 호출(틱 내 dict 캐시).
    - BotException(SubwayApiUnavailable 포함) → swallow + 로그. 그 외 예외 → 전파.
    """
    now = datetime.now(tz=timezone.utc)
    subway_client = SubwayClient(ctx.http_client, ctx.settings)

    async with ctx.session_maker() as session:
        repo = NotificationRepository(session)
        history_repo = NotificationHistoryRepository(session)

        subs = await repo.list_active_subscriptions_with_user(NotificationType.TRANSIT)
        _logger.info("transit_poll_tick", count=len(subs))

        # station_name → fetch_arrivals 결과를 틱 내 캐시해 중복 API 호출 방지.
        arrivals_cache: dict[str, object] = {}

        for notification, user in subs:
            cfg = notification.config
            mode: str = cfg.get("mode", "")
            if mode != "recurring":
                _logger.debug(
                    "transit_skip_non_recurring",
                    notification_id=notification.id,
                    mode=mode,
                )
                continue

            # 윈도우(start_time/end_time) 검사. UTC HH:MM 문자열 비교.
            start_time: str | None = cfg.get("start_time")
            end_time: str | None = cfg.get("end_time")
            if start_time is not None or end_time is not None:
                now_hhmm = now.strftime("%H:%M")
                if start_time is not None and now_hhmm < start_time:
                    _logger.debug(
                        "transit_skip_before_window",
                        notification_id=notification.id,
                        now_hhmm=now_hhmm,
                        start_time=start_time,
                    )
                    continue
                if end_time is not None and now_hhmm > end_time:
                    _logger.debug(
                        "transit_skip_after_window",
                        notification_id=notification.id,
                        now_hhmm=now_hhmm,
                        end_time=end_time,
                    )
                    continue

            # in_flight 체크: 이미 큐에 적재돼 처리 중인 구독 skip.
            if notification.id in ctx.in_flight_notification_ids:
                _logger.debug("transit_skip_in_flight", notification_id=notification.id)
                continue

            # 마지막 발송 시각 체크 — interval_minutes 미만이면 skip.
            interval_minutes: int = int(cfg.get("interval_minutes", 0))
            if interval_minutes > 0:
                last_sent_at = await history_repo.get_last_sent_at(
                    notification.id, NotificationDeliveryStatus.SUCCESS
                )
                if last_sent_at is not None:
                    elapsed_seconds = (now - last_sent_at).total_seconds()
                    if elapsed_seconds < interval_minutes * 60:
                        _logger.debug(
                            "transit_skip_interval_not_elapsed",
                            notification_id=notification.id,
                            elapsed_seconds=elapsed_seconds,
                            interval_seconds=interval_minutes * 60,
                        )
                        continue

            # SubwayClient 호출 — 동일 역 이름은 캐시 사용.
            station_name: str = cfg.get("station_name", "")
            line: str = cfg.get("line", "")

            if station_name not in arrivals_cache:
                try:
                    arrivals_cache[station_name] = await subway_client.fetch_arrivals(
                        station_name
                    )
                except SubwayApiUnavailable as exc:
                    _logger.warning(
                        "transit_subway_api_unavailable",
                        notification_id=notification.id,
                        station_name=station_name,
                        code=exc.code,
                    )
                    # BotException: swallow, 다음 틱 재시도.
                    continue
                except BotException as exc:
                    _logger.warning(
                        "transit_bot_exception",
                        notification_id=notification.id,
                        station_name=station_name,
                        code=exc.code,
                    )
                    continue

            raw_arrivals = arrivals_cache[station_name]
            from app.crawlers.subway.client import (
                SubwayArrival,
            )  # local import for type narrowing

            arrivals = raw_arrivals if isinstance(raw_arrivals, list) else []
            typed_arrivals: list[SubwayArrival] = [
                a for a in arrivals if isinstance(a, SubwayArrival)
            ]

            embed, payload = build_transit_recurring_embed(
                station_name=station_name,
                line=line,
                arrivals=typed_arrivals,
                now=now,
            )

            ctx.in_flight_notification_ids.add(notification.id)
            await ctx.queue.put(
                SendDmTask(
                    notification_id=notification.id,
                    user_id=user.id,
                    discord_id=user.discord_id,
                    embed=embed,
                    payload=payload,
                )
            )
            _logger.info(
                "transit_queued",
                notification_id=notification.id,
                user_id=user.id,
                station_name=station_name,
                line=line,
            )
