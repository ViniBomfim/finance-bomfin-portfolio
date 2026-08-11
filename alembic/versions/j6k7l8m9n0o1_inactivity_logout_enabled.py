"""inactivity logout enabled toggle

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-05-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j6k7l8m9n0o1"
down_revision: Union[str, None] = "i5j6k7l8m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO platform_settings (key, value) "
            "VALUES ('inactivity_logout_enabled', '1') "
            "ON CONFLICT (key) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM platform_settings WHERE key = 'inactivity_logout_enabled'")
    )
