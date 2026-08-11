"""notifications table

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-07-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q3r4s5t6u7v8"
down_revision: Union[str, None] = "p2q3r4s5t6u7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("modulo", sa.String(length=40), nullable=False),
        sa.Column("tipo", sa.String(length=80), nullable=False),
        sa.Column("severidade", sa.String(length=20), nullable=False),
        sa.Column("titulo", sa.String(length=300), nullable=False),
        sa.Column("subtitulo", sa.String(length=500), nullable=False),
        sa.Column("lida", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("link", sa.String(length=300), nullable=False),
        sa.Column("referencia_id", sa.String(length=64), nullable=False),
        sa.Column("lida_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index(
        "ix_notifications_user_tipo_ref_lida",
        "notifications",
        ["user_id", "tipo", "referencia_id", "lida"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_tipo_ref_lida", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
