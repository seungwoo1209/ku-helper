import asyncio
from unittest.mock import MagicMock

import httpx
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import SecretStr

from app.scheduler.context import JobContext
from app.scheduler.jobs import (
    IMMEDIATE_SEND_TICK_SECONDS,
    LIBRARY_TICK_SECONDS,
    LUNCH_TICK_SECONDS,
    TRANSIT_TICK_SECONDS,
    register_jobs,
)

_EXPECTED_INTERVAL_SECONDS = {
    "transit_poll": TRANSIT_TICK_SECONDS,
    "lunch_poll": LUNCH_TICK_SECONDS,
    "library_poll": LIBRARY_TICK_SECONDS,
    "immediate_send_lunch_poll": IMMEDIATE_SEND_TICK_SECONDS,
    "immediate_send_transit_poll": IMMEDIATE_SEND_TICK_SECONDS,
}


@pytest.fixture
def job_ctx() -> JobContext:
    """dummy JobContext 픽스처 — 잡 등록 검증에서만 사용, 실제 실행 안 함."""
    settings = MagicMock()
    settings.subway_api_key = SecretStr("test-key")

    return JobContext(
        queue=asyncio.Queue(),
        http_client=httpx.AsyncClient(),
        session_maker=MagicMock(),
        settings=settings,
        in_flight_notification_ids=set(),
    )


def test_register_jobs_registers_all_polling_jobs(job_ctx: JobContext) -> None:
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler, job_ctx)

    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == set(_EXPECTED_INTERVAL_SECONDS)


def test_register_jobs_uses_expected_intervals(job_ctx: JobContext) -> None:
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler, job_ctx)

    for job in scheduler.get_jobs():
        # 트리거가 IntervalTrigger인지 + 주기가 모듈 상수와 일치하는지 동시에 회귀 가드.
        assert isinstance(job.trigger, IntervalTrigger)
        expected = _EXPECTED_INTERVAL_SECONDS[job.id]
        assert job.trigger.interval.total_seconds() == expected


def test_register_jobs_sets_overlap_and_misfire_guards(job_ctx: JobContext) -> None:
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler, job_ctx)

    for job in scheduler.get_jobs():
        # max_instances=1: 짧은 틱 환경에서 이전 잡과 겹쳐 실행되는 회귀 방지.
        assert job.max_instances == 1
        # coalesce=True: 지연 후 누적된 트리거가 한 번에 폭주하는 회귀 방지.
        assert job.coalesce is True
        assert job.misfire_grace_time is not None


def test_immediate_send_transit_poll_registered_with_ctx(job_ctx: JobContext) -> None:
    """immediate_send_transit_poll 잡이 5초 인터벌 + args=[ctx] 로 등록되어야 한다."""
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler, job_ctx)

    job = next(
        (j for j in scheduler.get_jobs() if j.id == "immediate_send_transit_poll"), None
    )
    assert job is not None, "immediate_send_transit_poll 잡이 등록되지 않음"
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == IMMEDIATE_SEND_TICK_SECONDS
    # args 에 ctx 가 포함되어야 한다.
    assert job_ctx in job.args
