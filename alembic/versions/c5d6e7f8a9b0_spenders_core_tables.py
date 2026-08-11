"""spenders, shares, debtors, trips + colunas auxiliares

Revision ID: c5d6e7f8a9b0
Revises: c4d5e6f7a8b0
Create Date: 2026-05-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "c4d5e6f7a8b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.DateTime(timezone=True)
_TS_DEFAULT = sa.text("(CURRENT_TIMESTAMP)")


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table("card_transactions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("from_statement", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.create_table(
        "spenders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.Column("updated_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_spenders_user_id"), "spenders", ["user_id"], unique=False)
    op.create_index(op.f("ix_spenders_is_global"), "spenders", ["is_global"], unique=False)

    op.create_table(
        "card_transaction_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("valor", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("card_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("spender_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.Column("updated_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.ForeignKeyConstraint(["card_transaction_id"], ["card_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spender_id"], ["spenders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_card_transaction_shares_card_transaction_id"),
        "card_transaction_shares",
        ["card_transaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_card_transaction_shares_spender_id"),
        "card_transaction_shares",
        ["spender_id"],
        unique=False,
    )

    op.create_table(
        "expense_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("valor", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("expense_id", sa.Uuid(), nullable=False),
        sa.Column("spender_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.Column("updated_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spender_id"], ["spenders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_expense_shares_expense_id"), "expense_shares", ["expense_id"], unique=False)
    op.create_index(op.f("ix_expense_shares_spender_id"), "expense_shares", ["spender_id"], unique=False)

    op.create_table(
        "debtor_loans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("devedor_nome", sa.String(length=200), nullable=False),
        sa.Column("valor_emprestado", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("data_emprestimo", sa.Date(), nullable=False),
        sa.Column("destino_dinheiro", sa.String(length=500), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("spender_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.Column("updated_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spender_id"], ["spenders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_debtor_loans_user_id"), "debtor_loans", ["user_id"], unique=False)
    op.create_index(op.f("ix_debtor_loans_spender_id"), "debtor_loans", ["spender_id"], unique=False)

    op.create_table(
        "debtor_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("data_pagamento", sa.Date(), nullable=False),
        sa.Column("valor_pago", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("observacao", sa.String(length=500), nullable=True),
        sa.Column("emprestimo_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.Column("updated_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.ForeignKeyConstraint(["emprestimo_id"], ["debtor_loans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_debtor_payments_emprestimo_id"), "debtor_payments", ["emprestimo_id"], unique=False)

    op.create_table(
        "trips",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("destino", sa.String(length=200), nullable=True),
        sa.Column("data_inicio", sa.Date(), nullable=True),
        sa.Column("data_fim", sa.Date(), nullable=True),
        sa.Column("moeda_base", sa.String(length=8), nullable=False, server_default="BRL"),
        sa.Column("orcamento_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planning"),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.Column("updated_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trips_user_id"), "trips", ["user_id"], unique=False)

    op.create_table(
        "trip_participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("spender_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.Column("updated_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spender_id"], ["spenders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_id", "spender_id", name="uq_trip_participant"),
    )
    op.create_index(op.f("ix_trip_participants_trip_id"), "trip_participants", ["trip_id"], unique=False)
    op.create_index(op.f("ix_trip_participants_spender_id"), "trip_participants", ["spender_id"], unique=False)

    op.create_table(
        "trip_expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("descricao", sa.String(length=500), nullable=False),
        sa.Column("valor", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("moeda", sa.String(length=8), nullable=False, server_default="BRL"),
        sa.Column("taxa_cambio", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("valor_base", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("categoria", sa.String(length=20), nullable=False),
        sa.Column("forma_pagamento", sa.String(length=20), nullable=False, server_default="cash"),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("paid_by_spender_id", sa.Uuid(), nullable=False),
        sa.Column("pushed_expense_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.Column("updated_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paid_by_spender_id"], ["spenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pushed_expense_id"], ["expenses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trip_expenses_trip_id"), "trip_expenses", ["trip_id"], unique=False)
    op.create_index(op.f("ix_trip_expenses_user_id"), "trip_expenses", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_trip_expenses_paid_by_spender_id"), "trip_expenses", ["paid_by_spender_id"], unique=False
    )
    op.create_index(
        op.f("ix_trip_expenses_pushed_expense_id"), "trip_expenses", ["pushed_expense_id"], unique=False
    )

    op.create_table(
        "trip_expense_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("valor", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("trip_expense_id", sa.Uuid(), nullable=False),
        sa.Column("spender_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.Column("updated_at", _TS, server_default=_TS_DEFAULT, nullable=False),
        sa.ForeignKeyConstraint(["trip_expense_id"], ["trip_expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spender_id"], ["spenders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_trip_expense_shares_trip_expense_id"),
        "trip_expense_shares",
        ["trip_expense_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trip_expense_shares_spender_id"), "trip_expense_shares", ["spender_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("trip_expense_shares")
    op.drop_table("trip_expenses")
    op.drop_table("trip_participants")
    op.drop_table("trips")
    op.drop_table("debtor_payments")
    op.drop_table("debtor_loans")
    op.drop_table("expense_shares")
    op.drop_table("card_transaction_shares")
    op.drop_table("spenders")
    with op.batch_alter_table("card_transactions", schema=None) as batch_op:
        batch_op.drop_column("from_statement")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("is_admin")
