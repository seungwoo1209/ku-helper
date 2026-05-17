"""add users.status column

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_USER_STATUS_VALUES = ("ACTIVE", "DELETED")


def upgrade() -> None:
    user_status = sa.Enum(*_USER_STATUS_VALUES, name="user_status")
    user_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.Enum(*_USER_STATUS_VALUES, name="user_status", create_type=False),
            nullable=False,
            server_default="ACTIVE",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "status")
    sa.Enum(name="user_status").drop(op.get_bind(), checkfirst=True)
