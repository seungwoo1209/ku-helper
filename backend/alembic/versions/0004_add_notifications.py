"""add notifications and notification_history

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NOTIFICATION_TYPE_VALUES = ("TRANSIT", "LUNCH", "LIBRARY")
_DELIVERY_STATUS_VALUES = ("SUCCESS", "FAILED")


def upgrade() -> None:
    bind = op.get_bind()
    sa.Enum(*_NOTIFICATION_TYPE_VALUES, name="notification_type").create(
        bind, checkfirst=True
    )
    sa.Enum(*_DELIVERY_STATUS_VALUES, name="notification_delivery_status").create(
        bind, checkfirst=True
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum(
                *_NOTIFICATION_TYPE_VALUES,
                name="notification_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index(
        "ix_notifications_user_id_enabled",
        "notifications",
        ["user_id", "enabled"],
    )

    op.create_table(
        "notification_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "notification_id",
            sa.Integer(),
            sa.ForeignKey("notifications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                *_DELIVERY_STATUS_VALUES,
                name="notification_delivery_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_notification_history_notification_id",
        "notification_history",
        ["notification_id"],
    )
    op.create_index(
        "ix_notification_history_user_id_sent_at",
        "notification_history",
        ["user_id", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_history_user_id_sent_at",
        table_name="notification_history",
    )
    op.drop_index(
        "ix_notification_history_notification_id",
        table_name="notification_history",
    )
    op.drop_table("notification_history")

    op.drop_index("ix_notifications_user_id_enabled", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    bind = op.get_bind()
    sa.Enum(name="notification_delivery_status").drop(bind, checkfirst=True)
    sa.Enum(name="notification_type").drop(bind, checkfirst=True)
