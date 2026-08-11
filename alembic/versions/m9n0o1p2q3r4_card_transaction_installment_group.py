"""card_transactions: installment_group_id

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0p1q2r3
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m9n0o1p2q3r4"
down_revision: Union[str, None] = "l8m9n0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("card_transactions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("installment_group_id", sa.Uuid(), nullable=True))
        batch_op.create_index(
            "ix_card_transactions_installment_group_id",
            ["installment_group_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("card_transactions", schema=None) as batch_op:
        batch_op.drop_index("ix_card_transactions_installment_group_id")
        batch_op.drop_column("installment_group_id")
