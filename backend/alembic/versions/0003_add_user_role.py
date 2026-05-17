"""add users.role column

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_USER_ROLE_VALUES = ("USER", "ADMIN")


def upgrade() -> None:
    user_role = sa.Enum(*_USER_ROLE_VALUES, name="user_role")
    user_role.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.Enum(*_USER_ROLE_VALUES, name="user_role", create_type=False),
            nullable=False,
            server_default="USER",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
