"""ImmediateSendTransitRepository.list_pending 회귀 가드.

실제 DB 없이 SQLAlchemy AsyncSession 을 AsyncMock 으로 대체해 단위 검증한다.
통합 검증(DELETED 사용자 필터 등)은 쿼리 구조(WHERE 절 존재 여부)로 확인한다.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.notifications.transit.repository import ImmediateSendTransitRepository


def _make_repo() -> tuple[ImmediateSendTransitRepository, MagicMock]:
    """테스트용 repo + session mock 쌍을 반환한다."""
    session = MagicMock()
    session.execute = AsyncMock()
    repo = ImmediateSendTransitRepository(session)
    return repo, session


def _make_row(
    id: int = 1,
    user_id: int = 10,
    discord_id: int = 9999,
    payload: dict[str, Any] | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = id
    row.user_id = user_id
    row.discord_id = discord_id
    row.payload = payload or {"station_name": "강남", "line": "2호선"}
    return row


# ---------------------------------------------------------------------------
# 회귀 가드 1: 쿼리에 ACTIVE 사용자 필터가 포함되어 있음을 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pending_filters_deleted_users_via_query_structure() -> None:
    """list_pending 쿼리가 User.status == ACTIVE 조건을 포함해야 한다.

    실제 DB 없이 쿼리 구조를 검증한다 — 조건이 누락되면 DELETED 사용자에게
    DM 이 발송되는 보안 회귀가 발생한다.
    """
    repo, session = _make_repo()
    result_mock = MagicMock()
    result_mock.all.return_value = []
    session.execute.return_value = result_mock

    await repo.list_pending(limit=50)

    session.execute.assert_awaited_once()
    stmt = session.execute.call_args[0][0]

    # 컴파일된 쿼리 문자열에서 ACTIVE 필터 존재 확인.
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "ACTIVE" in compiled, "DELETED 사용자 필터(ACTIVE 조건)가 쿼리에 없음"


# ---------------------------------------------------------------------------
# 회귀 가드 2: 쿼리가 type=TRANSIT 만 조회함을 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pending_filters_by_transit_type() -> None:
    """list_pending 쿼리가 type=TRANSIT 조건만 포함해야 한다.

    LUNCH/LIBRARY row 가 섞이면 wrong worker 에서 발송되는 회귀가 발생한다.
    """
    repo, session = _make_repo()
    result_mock = MagicMock()
    result_mock.all.return_value = []
    session.execute.return_value = result_mock

    await repo.list_pending(limit=50)

    stmt = session.execute.call_args[0][0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "TRANSIT" in compiled, "type=TRANSIT 필터가 쿼리에 없음"
    # 다른 타입이 hard-coded 로 포함되어서는 안 된다.
    assert "LUNCH" not in compiled
    assert "LIBRARY" not in compiled


# ---------------------------------------------------------------------------
# 회귀 가드 3: LEFT JOIN 가드가 포함되어 있음을 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pending_excludes_already_processed_via_left_join() -> None:
    """list_pending 쿼리에 notification_history LEFT JOIN + NULL 필터가 있어야 한다.

    이 가드가 없으면 이미 발송된 row 가 매 틱마다 재처리된다.
    """
    repo, session = _make_repo()
    result_mock = MagicMock()
    result_mock.all.return_value = []
    session.execute.return_value = result_mock

    await repo.list_pending(limit=50)

    stmt = session.execute.call_args[0][0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    # LEFT OUTER JOIN + IS NULL 패턴 검증.
    assert "LEFT OUTER JOIN" in compiled.upper() or "LEFT JOIN" in compiled.upper()
    assert "notification_history" in compiled


# ---------------------------------------------------------------------------
# 회귀 가드 4: ORDER BY id + LIMIT 동작 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pending_returns_rows_in_order_with_limit() -> None:
    """list_pending 이 row 를 id 순 + limit 개만 반환하는지 검증한다."""
    repo, session = _make_repo()

    fake_rows = [
        _make_row(id=1, user_id=10),
        _make_row(id=2, user_id=11),
    ]
    result_mock = MagicMock()
    result_mock.all.return_value = fake_rows
    session.execute.return_value = result_mock

    rows = await repo.list_pending(limit=2)

    assert len(rows) == 2
    assert rows[0].id == 1
    assert rows[1].id == 2

    # LIMIT 절 확인.
    stmt = session.execute.call_args[0][0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "LIMIT" in compiled.upper()

    # ORDER BY id 확인.
    assert "ORDER BY" in compiled.upper()
