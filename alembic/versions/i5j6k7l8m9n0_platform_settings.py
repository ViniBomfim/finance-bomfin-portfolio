"""platform settings: inactivity logout timeout

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-05-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "i5j6k7l8m9n0"
down_revision: Union[str, None] = "h4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table("platform_settings"):
        op.create_table(
            "platform_settings",
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("value", sa.String(length=64), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("key"),
        )
    if bind.dialect.name == "sqlite":
        op.execute(
            sa.text(
                "INSERT OR IGNORE INTO platform_settings (key, value) "
                "VALUES ('inactivity_logout_minutes', '60')"
            )
        )
    else:
        op.execute(
            sa.text(
                "INSERT INTO platform_settings (key, value) "
                "VALUES ('inactivity_logout_minutes', '60') "
                "ON CONFLICT (key) DO NOTHING"
            )
        )


def downgrade() -> None:
    op.drop_table("platform_settings")
