from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.scheduler.jobs import (
    LIBRARY_TICK_SECONDS,
    LUNCH_TICK_SECONDS,
    TRANSIT_TICK_SECONDS,
    register_jobs,
)

_EXPECTED_INTERVAL_SECONDS = {
    "transit_poll": TRANSIT_TICK_SECONDS,
    "lunch_poll": LUNCH_TICK_SECONDS,
    "library_poll": LIBRARY_TICK_SECONDS,
}


def test_register_jobs_registers_three_polling_jobs() -> None:
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler)

    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == set(_EXPECTED_INTERVAL_SECONDS)


def test_register_jobs_uses_expected_intervals() -> None:
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler)

    for job in scheduler.get_jobs():
        # 트리거가 IntervalTrigger인지 + 주기가 모듈 상수와 일치하는지 동시에 회귀 가드.
        assert isinstance(job.trigger, IntervalTrigger)
        expected = _EXPECTED_INTERVAL_SECONDS[job.id]
        assert job.trigger.interval.total_seconds() == expected


def test_register_jobs_sets_overlap_and_misfire_guards() -> None:
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler)

    for job in scheduler.get_jobs():
        # max_instances=1: 짧은 틱 환경에서 이전 잡과 겹쳐 실행되는 회귀 방지.
        assert job.max_instances == 1
        # coalesce=True: 지연 후 누적된 트리거가 한 번에 폭주하는 회귀 방지.
        assert job.coalesce is True
        assert job.misfire_grace_time is not None
