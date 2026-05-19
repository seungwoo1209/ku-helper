"""baseline users table

Revision ID: 0001
Revises:
Create Date: 2026-05-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_username", sa.String(length=100), nullable=False),
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
        sa.UniqueConstraint("discord_id", name="uq_users_discord_id"),
    )
    op.create_index("ix_users_discord_id", "users", ["discord_id"])


def downgrade() -> None:
    op.drop_index("ix_users_discord_id", table_name="users")
    op.drop_table("users")
