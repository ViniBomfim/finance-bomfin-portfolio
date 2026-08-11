"""investments FII: quantidade, preco_medio, preco_unitario_atual

Revision ID: c2d3e4f5a6b1
Revises: b1c2d3e4f5a0
Create Date: 2026-05-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b1"
down_revision: Union[str, None] = "b1c2d3e4f5a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("investments", sa.Column("quantidade", sa.Numeric(18, 8), nullable=True))
    op.add_column("investments", sa.Column("preco_medio", sa.Numeric(14, 6), nullable=True))
    op.add_column("investments", sa.Column("preco_unitario_atual", sa.Numeric(14, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("investments", "preco_unitario_atual")
    op.drop_column("investments", "preco_medio")
    op.drop_column("investments", "quantidade")
