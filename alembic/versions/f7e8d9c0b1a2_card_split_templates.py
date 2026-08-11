"""card_split_templates

Revision ID: f7e8d9c0b1a2
Revises: e8f9a0b1c2d3
Create Date: 2026-04-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7e8d9c0b1a2"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_split_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("description_key", sa.String(length=500), nullable=False),
        sa.Column("parts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "card_id", "description_key", name="uq_card_split_tpl_desc"),
    )
    op.create_index("ix_card_split_templates_user_id", "card_split_templates", ["user_id"], unique=False)
    op.create_index("ix_card_split_templates_card_id", "card_split_templates", ["card_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_card_split_templates_card_id", table_name="card_split_templates")
    op.drop_index("ix_card_split_templates_user_id", table_name="card_split_templates")
    op.drop_table("card_split_templates")
