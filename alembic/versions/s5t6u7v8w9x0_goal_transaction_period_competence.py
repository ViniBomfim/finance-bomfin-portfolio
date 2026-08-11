"""goal_transactions.period_id + incomes.origem_meta (competência mensal das metas)

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
Create Date: 2026-08-10

"""

from datetime import date, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "s5t6u7v8w9x0"
down_revision: Union[str, None] = "r4s5t6u7v8w9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    gt_cols = {c["name"] for c in insp.get_columns("goal_transactions")}
    if "period_id" not in gt_cols:
        with op.batch_alter_table("goal_transactions", schema=None) as batch_op:
            batch_op.add_column(sa.Column("period_id", sa.Uuid(), nullable=True))
            batch_op.create_foreign_key(
                "fk_goal_transactions_period_id",
                "periods",
                ["period_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index("ix_goal_transactions_period_id", ["period_id"])

    inc_cols = {c["name"] for c in inspect(bind).get_columns("incomes")}
    if "origem_meta" not in inc_cols:
        with op.batch_alter_table("incomes", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "origem_meta",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false") if bind.dialect.name != "sqlite" else sa.text("0"),
                )
            )

    backfill_goal_period_competence(bind)


def backfill_goal_period_competence(bind: sa.engine.Connection) -> None:
    """Atribui competência às transações antigas e marca as receitas vindas de retirada."""
    periods = {
        (str(user_id), int(ano), int(mes)): period_id
        for period_id, user_id, mes, ano in bind.execute(
            sa.text("SELECT id, user_id, mes, ano FROM periods")
        )
    }
    if periods:
        pending = bind.execute(
            sa.text("SELECT id, user_id, data FROM goal_transactions WHERE period_id IS NULL")
        ).fetchall()
        for tx_id, user_id, data in pending:
            parsed = _as_date(data)
            if parsed is None:
                continue
            period_id = periods.get((str(user_id), parsed.year, parsed.month))
            if period_id is None:
                continue
            bind.execute(
                sa.text("UPDATE goal_transactions SET period_id = :period_id WHERE id = :tx_id"),
                {"period_id": period_id, "tx_id": tx_id},
            )

    bind.execute(
        sa.text(
            """
            UPDATE incomes
            SET origem_meta = :truthy
            WHERE id IN (SELECT income_id FROM goal_transactions WHERE income_id IS NOT NULL)
            """
        ),
        {"truthy": True},
    )


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def downgrade() -> None:
    with op.batch_alter_table("incomes", schema=None) as batch_op:
        batch_op.drop_column("origem_meta")

    with op.batch_alter_table("goal_transactions", schema=None) as batch_op:
        batch_op.drop_index("ix_goal_transactions_period_id")
        batch_op.drop_constraint("fk_goal_transactions_period_id", type_="foreignkey")
        batch_op.drop_column("period_id")
