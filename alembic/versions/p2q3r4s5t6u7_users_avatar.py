"""users.avatar_bytes + avatar_content_type

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-07-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p2q3r4s5t6u7"
down_revision: Union[str, None] = "o1p2q3r4s5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("avatar_bytes", sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column("avatar_content_type", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("avatar_content_type")
        batch_op.drop_column("avatar_bytes")
