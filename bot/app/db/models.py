"""백엔드 스키마 duplicate.

봇은 마이그레이션 권한이 없다. 백엔드의 `app/domains/users/models.py`,
`app/domains/notifications/models.py`와 형상을 동기화하는 책임은 백엔드 PR 작성자에게 있다.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    discord_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    discord_username: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class NotificationType(StrEnum):
    TRANSIT = "TRANSIT"
    LUNCH = "LUNCH"
    LIBRARY = "LIBRARY"


class NotificationDeliveryStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_id_enabled", "user_id", "enabled"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImmediateSendRequest(Base):
    """백엔드 0005 마이그레이션의 immediate_send_requests 와 형상 일치.

    봇은 SELECT 만 — INSERT/UPDATE/DELETE 메서드를 정의하지 않는다.
    """

    __tablename__ = "immediate_send_requests"
    __table_args__ = (Index("ix_immediate_send_requests_type_id", "type", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", create_type=False),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NotificationHistory(Base):
    __tablename__ = "notification_history"
    __table_args__ = (
        Index(
            "ix_notification_history_user_id_sent_at",
            "user_id",
            "sent_at",
        ),
        Index(
            "uq_notification_history_immediate_send_request_id",
            "immediate_send_request_id",
            unique=True,
            postgresql_where="immediate_send_request_id IS NOT NULL",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("notifications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    immediate_send_request_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("immediate_send_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[NotificationDeliveryStatus] = mapped_column(
        Enum(NotificationDeliveryStatus, name="notification_delivery_status"),
        nullable=False,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
