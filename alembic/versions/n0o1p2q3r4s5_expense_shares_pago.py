"""expense_shares.pago

Revision ID: n0o1p2q3r4s5
Revises: m9n0o1p2q3r4
Create Date: 2026-07-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n0o1p2q3r4s5"
down_revision: Union[str, None] = "m9n0o1p2q3r4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("expense_shares") as batch_op:
        batch_op.add_column(
            sa.Column("pago", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    # Backfill: shares herdam o status do gasto.
    op.execute(
        """
        UPDATE expense_shares
        SET pago = TRUE
        WHERE expense_id IN (SELECT id FROM expenses WHERE pago IS TRUE)
        """
    )
    op.execute(
        """
        UPDATE expense_shares
        SET pago = FALSE
        WHERE expense_id IN (SELECT id FROM expenses WHERE pago IS FALSE)
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("expense_shares") as batch_op:
        batch_op.drop_column("pago")
