"""users: goal_pool_withdrawn_to_income for meta pool accounting

Revision ID: l8m9n0p1q2r3
Revises: k7l8m9n0o1p2
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "l8m9n0p1q2r3"
down_revision: Union[str, None] = "k7l8m9n0o1p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("users")}
    if "goal_pool_withdrawn_to_income" in cols:
        return
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "goal_pool_withdrawn_to_income",
                sa.Numeric(precision=14, scale=2),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("goal_pool_withdrawn_to_income")
