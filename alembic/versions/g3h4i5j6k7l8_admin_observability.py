"""admin observability: error logs, access logs, user login stats

Revision ID: g3h4i5j6k7l8
Revises: f1a2b3c4d5e6
Create Date: 2026-05-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g3h4i5j6k7l8"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("login_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "system_error_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_error_logs_created_at", "system_error_logs", ["created_at"], unique=False)
    op.create_index("ix_system_error_logs_path", "system_error_logs", ["path"], unique=False)
    op.create_index("ix_system_error_logs_status_code", "system_error_logs", ["status_code"], unique=False)
    op.create_index("ix_system_error_logs_user_id", "system_error_logs", ["user_id"], unique=False)

    op.create_table(
        "user_access_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_access_logs_user_id", "user_access_logs", ["user_id"], unique=False)
    op.create_index("ix_user_access_logs_event_type", "user_access_logs", ["event_type"], unique=False)
    op.create_index("ix_user_access_logs_created_at", "user_access_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_access_logs_created_at", table_name="user_access_logs")
    op.drop_index("ix_user_access_logs_event_type", table_name="user_access_logs")
    op.drop_index("ix_user_access_logs_user_id", table_name="user_access_logs")
    op.drop_table("user_access_logs")
    op.drop_index("ix_system_error_logs_user_id", table_name="system_error_logs")
    op.drop_index("ix_system_error_logs_status_code", table_name="system_error_logs")
    op.drop_index("ix_system_error_logs_path", table_name="system_error_logs")
    op.drop_index("ix_system_error_logs_created_at", table_name="system_error_logs")
    op.drop_table("system_error_logs")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("login_count")
