"""card_transactions: data + pago

Revision ID: c4d5e6f7a8b0
Revises: b2c3d4e5f6a8
Create Date: 2026-04-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b0"
down_revision: Union[str, None] = "b2c3d4e5f6a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("card_transactions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("data", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("pago", sa.Boolean(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE card_transactions
            SET data = CAST(created_at AS DATE)
            WHERE data IS NULL
        """)
    )
    conn.execute(
        sa.text("""
            UPDATE card_transactions
            SET pago = TRUE
            WHERE pago IS NULL
        """)
    )

    with op.batch_alter_table("card_transactions", schema=None) as batch_op:
        batch_op.alter_column("data", existing_type=sa.Date(), nullable=False)
        batch_op.alter_column("pago", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("card_transactions", schema=None) as batch_op:
        batch_op.drop_column("pago")
        batch_op.drop_column("data")
