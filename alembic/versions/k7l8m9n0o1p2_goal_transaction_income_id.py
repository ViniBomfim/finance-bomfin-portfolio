"""goal_transactions: income_id for withdraw-as-income

Revision ID: k7l8m9n0o1p2
Revises: j6k7l8m9n0o1
Create Date: 2026-06-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "k7l8m9n0o1p2"
down_revision: Union[str, None] = "j6k7l8m9n0o1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("goal_transactions")}
    if "income_id" in cols:
        return

    with op.batch_alter_table("goal_transactions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("income_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_goal_transactions_income_id",
            "incomes",
            ["income_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_goal_transactions_income_id", ["income_id"])


def downgrade() -> None:
    with op.batch_alter_table("goal_transactions", schema=None) as batch_op:
        batch_op.drop_index("ix_goal_transactions_income_id")
        batch_op.drop_constraint("fk_goal_transactions_income_id", type_="foreignkey")
        batch_op.drop_column("income_id")
