"""add immediate_send_requests and notification_history.immediate_send_request_id

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "immediate_send_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(
                "TRANSIT",
                "LUNCH",
                "LIBRARY",
                name="notification_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_immediate_send_requests_user_id",
        "immediate_send_requests",
        ["user_id"],
    )
    op.create_index(
        "ix_immediate_send_requests_type_id",
        "immediate_send_requests",
        ["type", "id"],
    )

    op.add_column(
        "notification_history",
        sa.Column(
            "immediate_send_request_id",
            sa.Integer(),
            sa.ForeignKey("immediate_send_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "uq_notification_history_immediate_send_request_id",
        "notification_history",
        ["immediate_send_request_id"],
        unique=True,
        postgresql_where=sa.text("immediate_send_request_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_notification_history_immediate_send_request_id",
        table_name="notification_history",
    )
    op.drop_column("notification_history", "immediate_send_request_id")
    op.drop_index(
        "ix_immediate_send_requests_type_id", table_name="immediate_send_requests"
    )
    op.drop_index(
        "ix_immediate_send_requests_user_id", table_name="immediate_send_requests"
    )
    op.drop_table("immediate_send_requests")
