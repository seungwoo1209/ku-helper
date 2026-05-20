"""build_library_embed 테스트 — F-15 긴급 색상/키워드 회귀 가드."""

from datetime import datetime, timezone

import discord

from app.crawlers.library.client import RoomSeats
from app.notifications.library.embeds import build_library_embed

_NOW = datetime(2026, 5, 20, 3, 0, tzinfo=timezone.utc)


def _room(available: int) -> RoomSeats:
    return RoomSeats(room_number=1, label="제1열람실", total=400, available=available)


def test_normal_embed_not_urgent() -> None:
    embed, payload = build_library_embed(
        _room(15), threshold=20, urgent_threshold=5, now=_NOW
    )

    assert embed.color == discord.Color.orange()
    assert "긴급" not in (embed.title or "")
    assert payload["is_urgent"] is False


def test_urgent_embed_red_and_keyword() -> None:
    """잔여 ≤ urgent_threshold → 빨강 + '긴급' 키워드."""
    embed, payload = build_library_embed(
        _room(3), threshold=20, urgent_threshold=5, now=_NOW
    )

    assert embed.color == discord.Color.red()
    assert "긴급" in (embed.title or "")
    assert payload["is_urgent"] is True


def test_payload_snapshot_fields() -> None:
    _, payload = build_library_embed(
        _room(15), threshold=20, urgent_threshold=5, now=_NOW
    )

    assert payload["room_number"] == 1
    assert payload["available"] == 15
    assert payload["total"] == 400
    assert payload["threshold"] == 20
    assert payload["urgent_threshold"] == 5
    assert payload["rendered_at"] == _NOW.isoformat()


def test_no_urgent_threshold_never_urgent() -> None:
    """urgent_threshold 가 None 이면 잔여가 0이어도 긴급 아님."""
    embed, payload = build_library_embed(
        _room(0), threshold=20, urgent_threshold=None, now=_NOW
    )

    assert embed.color == discord.Color.orange()
    assert payload["is_urgent"] is False
