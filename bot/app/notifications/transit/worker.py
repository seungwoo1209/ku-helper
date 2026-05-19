"""TRANSIT 알림 워커 — F-07 정기 간격(recurring) 모드 + 즉시 발송 모드.

Scheduler → Worker → (SubwayClient · Repository) → Sender 순서를 따른다.
F-18 활성 시간대·Redis 캐시는 후속 PR 에서 추가한다.
"""

from datetime import datetime, timezone
from datetime import time as datetime_time
from zoneinfo import ZoneInfo

import structlog

from app.core.exceptions import BotException
from app.crawlers.subway.client import SubwayArrival, SubwayClient
from app.crawlers.subway.exceptions import SubwayApiUnavailable
from app.db.models import NotificationDeliveryStatus, NotificationType
from app.notifications.history_repository import NotificationHistoryRepository
from app.notifications.repository import NotificationRepository
from app.notifications.sender import SendDmTask
from app.notifications.transit.embeds import build_transit_recurring_embed
from app.notifications.transit.repository import ImmediateSendTransitRepository
from app.scheduler.context import JobContext

_logger = structlog.get_logger(__name__)

# 사용자가 입력한 start_time/end_time 은 KST 기준.
_DISPLAY_TIMEZONE = ZoneInfo("Asia/Seoul")


def _parse_config_time(raw: str | None) -> datetime_time | None:
    """config JSONB 의 'HH:MM' 또는 'HH:MM:SS' 문자열 → datetime.time.

    Pydantic time 직렬화는 HH:MM:SS, 사용자가 직접 INSERT 한 경우 HH:MM 도 허용.
    """
    if raw is None:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None


async def run_transit_job(ctx: JobContext) -> None:
    """TRANSIT 활성 구독을 폴링하여 F-07 조건 충족 시 Sender 큐에 적재한다.

    - mode == "recurring" 만 처리. "arrival" 은 skip(F-06 후속 PR).
    - 같은 역(station) 구독이 여러 개이면 fetch_arrivals 는 한 번만 호출(틱 내 dict 캐시).
    - BotException(SubwayApiUnavailable 포함) → swallow + 로그. 그 외 예외 → 전파.
    """
    now = datetime.now(tz=timezone.utc)
    # 윈도우 비교는 KST 기준. UTC now 는 interval 계산에도 그대로 사용.
    now_kst_time = now.astimezone(_DISPLAY_TIMEZONE).time()
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

            # 윈도우(start_time/end_time) 검사. 사용자가 KST 기준으로 입력한 값과 비교.
            start_time = _parse_config_time(cfg.get("start_time"))
            end_time = _parse_config_time(cfg.get("end_time"))
            if start_time is not None and now_kst_time < start_time:
                _logger.debug(
                    "transit_skip_before_window",
                    notification_id=notification.id,
                    now_kst_time=now_kst_time.isoformat(),
                    start_time=start_time.isoformat(),
                )
                continue
            if end_time is not None and now_kst_time > end_time:
                _logger.debug(
                    "transit_skip_after_window",
                    notification_id=notification.id,
                    now_kst_time=now_kst_time.isoformat(),
                    end_time=end_time.isoformat(),
                )
                continue

            # in_flight 체크: 이미 큐에 적재돼 처리 중인 구독 skip.
            if notification.id in ctx.in_flight_notification_ids:
                _logger.debug("transit_skip_in_flight", notification_id=notification.id)
                continue

            # 마지막 발송 시각 체크 — repeat_interval_minutes 미만이면 skip.
            repeat_interval_minutes: int = int(cfg.get("repeat_interval_minutes", 0))
            if repeat_interval_minutes > 0:
                last_sent_at = await history_repo.get_last_sent_at(
                    notification.id, NotificationDeliveryStatus.SUCCESS
                )
                if last_sent_at is not None:
                    elapsed_seconds = (now - last_sent_at).total_seconds()
                    if elapsed_seconds < repeat_interval_minutes * 60:
                        _logger.debug(
                            "transit_skip_interval_not_elapsed",
                            notification_id=notification.id,
                            elapsed_seconds=elapsed_seconds,
                            interval_seconds=repeat_interval_minutes * 60,
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


async def run_immediate_send_transit_job(ctx: JobContext) -> None:
    """TRANSIT 즉시 발송 큐를 폴링하여 SubwayClient 결과를 Sender 에 적재.

    아키텍처 예외: crawler 실패 시 워커가 직접 NotificationHistoryRepository.insert_result
    (status=FAILED) 를 호출한다. 이유: embed/payload 가 없어 SendDmTask 를 만들 수 없으면
    history row 없이 LEFT JOIN 가드가 풀리지 않아 매 5초 재시도되기 때문. lunch 워커와 동일.
    정식 정리 후보: SendDmTask 에 "이미 실패" 플래그를 두고 Sender 가 INSERT 만 수행.
    """
    subway_client = SubwayClient(ctx.http_client, ctx.settings)
    now = datetime.now(tz=timezone.utc)

    try:
        async with ctx.session_maker() as session:
            repo = ImmediateSendTransitRepository(session)
            history_repo = NotificationHistoryRepository(session)
            rows = await repo.list_pending(limit=50)
            _logger.info("immediate_send_transit_tick", count=len(rows))

            for row in rows:
                if row.id in ctx.immediate_send_inflight:
                    _logger.debug(
                        "immediate_send_transit_skip_in_flight", request_id=row.id
                    )
                    continue
                ctx.immediate_send_inflight.add(row.id)

                station_name = str(row.payload.get("station_name", ""))
                line = str(row.payload.get("line", ""))

                try:
                    arrivals = await subway_client.fetch_arrivals(station_name)
                except (SubwayApiUnavailable, BotException) as exc:
                    _logger.warning(
                        "immediate_send_transit_subway_unavailable",
                        request_id=row.id,
                        station_name=station_name,
                        code=exc.code,
                    )
                    await history_repo.insert_result(
                        notification_id=None,
                        user_id=row.user_id,
                        status=NotificationDeliveryStatus.FAILED,
                        payload={"reason": "subway_api_unavailable", "code": exc.code},
                        failure_reason=exc.code,
                        immediate_send_request_id=row.id,
                    )
                    await session.commit()
                    ctx.immediate_send_inflight.discard(row.id)
                    continue

                embed, payload = build_transit_recurring_embed(
                    station_name=station_name,
                    line=line,
                    arrivals=arrivals,
                    now=now,
                )
                await ctx.queue.put(
                    SendDmTask(
                        notification_id=None,
                        user_id=row.user_id,
                        discord_id=row.discord_id,
                        embed=embed,
                        payload=payload,
                        immediate_send_request_id=row.id,
                    )
                )
                _logger.info(
                    "immediate_send_transit_queued",
                    request_id=row.id,
                    user_id=row.user_id,
                    station_name=station_name,
                    line=line,
                )
    except BotException as exc:
        _logger.exception("immediate_send_transit_failed", code=exc.code)
