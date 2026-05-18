from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.notifications.library.worker import run_library_job
from app.notifications.lunch.worker import run_lunch_job
from app.notifications.transit.worker import run_transit_job

# 알림 종류별 폴링 주기. TRANSIT/LIBRARY 는 외부 데이터 변화에 빨리 반응해야 하고,
# LUNCH 는 notify_at 정밀도가 분 단위라 분당 1회로 충분하다.
TRANSIT_TICK_SECONDS = 5
LIBRARY_TICK_SECONDS = 5
LUNCH_TICK_SECONDS = 60

# 지연 트리거 grace. 이 시간을 넘기면 해당 틱은 skip(coalesce 와 함께 백로그 쌓임 방지).
_MISFIRE_GRACE_SECONDS = 5


def register_jobs(scheduler: AsyncIOScheduler) -> None:
    """알림 종류별 정적 폴링 잡을 등록한다. lifespan 에서 1회만 호출.

    런타임에 `add_job`/`remove_job` 으로 잡을 동적 조작하지 않는다 — 알림 행 추가·삭제는
    각 잡 트리거에서 도는 `list_active_subscriptions` SELECT 결과 변화로 자동 반영된다.
    (architecture.md Scheduler 절)
    """
    scheduler.add_job(
        run_transit_job,
        trigger=IntervalTrigger(seconds=TRANSIT_TICK_SECONDS),
        id="transit_poll",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=_MISFIRE_GRACE_SECONDS,
    )
    scheduler.add_job(
        run_lunch_job,
        trigger=IntervalTrigger(seconds=LUNCH_TICK_SECONDS),
        id="lunch_poll",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=_MISFIRE_GRACE_SECONDS,
    )
    scheduler.add_job(
        run_library_job,
        trigger=IntervalTrigger(seconds=LIBRARY_TICK_SECONDS),
        id="library_poll",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=_MISFIRE_GRACE_SECONDS,
    )
