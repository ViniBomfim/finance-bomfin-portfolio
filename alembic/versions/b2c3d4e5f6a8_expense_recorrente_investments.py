"""expense recorrente + investments table

Revision ID: b2c3d4e5f6a8
Revises: d812e651629a
Create Date: 2026-04-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a8"
down_revision: Union[str, None] = "d812e651629a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column("recorrente", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "investments",
        sa.Column("descricao", sa.String(length=200), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("valor_aplicado", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("valor_atual", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_investments_user_id"), "investments", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_investments_user_id"), table_name="investments")
    op.drop_table("investments")
    op.drop_column("expenses", "recorrente")
