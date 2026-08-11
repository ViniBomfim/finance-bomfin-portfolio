"""card_transaction_shares.pago

Revision ID: o1p2q3r4s5t6
Revises: n0o1p2q3r4s5
Create Date: 2026-07-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o1p2q3r4s5t6"
down_revision: Union[str, None] = "n0o1p2q3r4s5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("card_transaction_shares") as batch_op:
        batch_op.add_column(
            sa.Column("pago", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.execute(
        """
        UPDATE card_transaction_shares
        SET pago = TRUE
        WHERE card_transaction_id IN (SELECT id FROM card_transactions WHERE pago IS TRUE)
        """
    )
    op.execute(
        """
        UPDATE card_transaction_shares
        SET pago = FALSE
        WHERE card_transaction_id IN (SELECT id FROM card_transactions WHERE pago IS FALSE)
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("card_transaction_shares") as batch_op:
        batch_op.drop_column("pago")
