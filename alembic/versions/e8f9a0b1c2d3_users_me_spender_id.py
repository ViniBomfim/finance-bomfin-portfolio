"""users: me_spender_id

Revision ID: e8f9a0b1c2d3
Revises: c4d5e6f7a8b0
Create Date: 2026-04-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("me_spender_id", sa.Uuid(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_users_me_spender_id_spenders",
            "spenders",
            ["me_spender_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_users_me_spender_id", ["me_spender_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_me_spender_id")
        batch_op.drop_constraint("fk_users_me_spender_id_spenders", type_="foreignkey")
        batch_op.drop_column("me_spender_id")
