"""user username and account_status

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-05-24

"""
from typing import Sequence, Union
import re

import sqlalchemy as sa
from alembic import op

revision: str = "h4i5j6k7l8m9"
down_revision: Union[str, None] = "g3h4i5j6k7l8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slug_from_email(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    slug = re.sub(r"[^a-z0-9_]", "_", local).strip("_")
    return (slug or "user")[:64]


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "account_status",
                sa.String(length=16),
                nullable=False,
                server_default="active",
            )
        )

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    used: set[str] = set()
    for row in rows:
        user_id, email = row[0], row[1]
        base = _slug_from_email(email)
        candidate = base
        n = 1
        while candidate in used:
            suffix = f"_{n}"
            candidate = f"{base[: max(1, 64 - len(suffix))]}{suffix}"
            n += 1
        used.add(candidate)
        conn.execute(
            sa.text("UPDATE users SET username = :username, account_status = 'active' WHERE id = :id"),
            {"username": candidate, "id": user_id},
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("username", nullable=False)
        batch_op.create_index("ix_users_username", ["username"], unique=True)
        batch_op.create_index("ix_users_account_status", ["account_status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_account_status")
        batch_op.drop_index("ix_users_username")
        batch_op.drop_column("account_status")
        batch_op.drop_column("username")
