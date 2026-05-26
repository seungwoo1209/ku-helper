"""F-17 윈도우 보정 정책 단위 테스트.

Service 의 `_resolve_window` 는 (date_from, date_to) 두 입력으로 sent_at 비교용
tz-aware datetime 쌍을 만든다. time-machine 으로 `now()` 를 고정해 결정적으로 검증.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
import time_machine

from app.domains.notifications.exceptions import InvalidHistoryDateRange
from app.domains.notifications.service import NotificationService

_FIXED_NOW = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)


@time_machine.travel(_FIXED_NOW, tick=False)
def test_default_window_is_last_30_days() -> None:
    sent_at_from, sent_at_to = NotificationService._resolve_window(None, None)
    assert sent_at_to == _FIXED_NOW
    assert sent_at_from == _FIXED_NOW - timedelta(days=30)


def test_only_date_from_pads_forward_30_days() -> None:
    sent_at_from, sent_at_to = NotificationService._resolve_window(
        date(2026, 5, 1), None
    )
    assert sent_at_from == datetime(2026, 5, 1, tzinfo=timezone.utc)
    assert sent_at_to == datetime(2026, 5, 1, tzinfo=timezone.utc) + timedelta(days=30)


def test_only_date_to_pads_back_30_days_inclusive() -> None:
    sent_at_from, sent_at_to = NotificationService._resolve_window(
        None, date(2026, 5, 26)
    )
    # date_to 는 inclusive day → 다음 자정 직전까지 포함하기 위해 +1d.
    assert sent_at_to == datetime(2026, 5, 27, tzinfo=timezone.utc)
    assert sent_at_from == sent_at_to - timedelta(days=30)


def test_inverted_range_raises() -> None:
    with pytest.raises(InvalidHistoryDateRange):
        NotificationService._resolve_window(date(2026, 5, 20), date(2026, 5, 10))


def test_range_over_30_days_raises() -> None:
    # 4/25 ~ 5/26 = 31일 (inclusive +1d 로 환산하면 32일 윈도우) → 거절.
    with pytest.raises(InvalidHistoryDateRange):
        NotificationService._resolve_window(date(2026, 4, 25), date(2026, 5, 26))


def test_exactly_30_day_range_accepted() -> None:
    # 4/27 ~ 5/26 = 30일. 경계 안쪽이라 통과해야 한다.
    sent_at_from, sent_at_to = NotificationService._resolve_window(
        date(2026, 4, 27), date(2026, 5, 26)
    )
    assert sent_at_to - sent_at_from == timedelta(days=30)
    assert sent_at_from == datetime.combine(
        date(2026, 4, 27), time.min, tzinfo=timezone.utc
    )
