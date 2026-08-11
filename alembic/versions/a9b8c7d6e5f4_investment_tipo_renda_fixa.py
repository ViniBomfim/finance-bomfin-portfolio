"""investment tipo other -> renda_fixa

Revision ID: a9b8c7d6e5f4
Revises: f7e8d9c0b1a2
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "f7e8d9c0b1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE investments SET tipo = 'renda_fixa' WHERE tipo = 'other'")


def downgrade() -> None:
    """Sem reversão segura: novas posições em renda_fixa não podem ser distinguidas das migradas de other."""
    pass
