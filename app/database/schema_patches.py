"""Ajustes incrementais para bancos já existentes (ex.: SQLite antes da coluna `recorrente`)."""

import json
import uuid
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import inspect, text

from sqlalchemy.engine import Engine

# Mesmo namespace da migração Alembic `b1c2d3e4f5a0_listed_assets_catalog.py` (IDs estáveis do seed).
_LISTED_ASSET_NS = uuid.UUID("019b0000-0000-7000-8000-000000000001")


def _listed_asset_pk(tipo: str, codigo: str) -> str:
    return str(uuid.uuid5(_LISTED_ASSET_NS, f"{tipo}:{codigo.upper()}"))


def _ensure_listed_assets_sqlite(engine: Engine) -> None:
    """Cria catálogo de ativos, coluna em investments e seed — para DBs sem Alembic completo."""
    insp = inspect(engine)
    if not insp.has_table("listed_assets"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE listed_assets (
                        id TEXT NOT NULL PRIMARY KEY,
                        codigo VARCHAR(32) NOT NULL,
                        nome VARCHAR(200) NOT NULL,
                        tipo VARCHAR(20) NOT NULL
                    )
                    """
                )
            )
            conn.execute(text("CREATE UNIQUE INDEX ix_listed_assets_codigo ON listed_assets (codigo)"))
            conn.execute(text("CREATE INDEX ix_listed_assets_tipo ON listed_assets (tipo)"))

    insp = inspect(engine)
    if insp.has_table("investments"):
        inv_cols = {c["name"] for c in insp.get_columns("investments")}
        if "listed_asset_id" not in inv_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE investments ADD COLUMN listed_asset_id TEXT "
                        "REFERENCES listed_assets(id) ON DELETE SET NULL"
                    )
                )
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_investments_listed_asset_id ON investments (listed_asset_id)")
                )

    insp = inspect(engine)
    if not insp.has_table("listed_assets"):
        return
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM listed_assets")).scalar_one()
    if n and int(n) > 0:
        return
    seed_path = Path(__file__).resolve().parent.parent / "data" / "listed_assets_seed.json"
    if not seed_path.is_file():
        return
    with open(seed_path, encoding="utf-8") as f:
        seed_rows = json.load(f)
    with engine.begin() as conn:
        for r in seed_rows:
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO listed_assets (id, codigo, nome, tipo) "
                    "VALUES (:id, :codigo, :nome, :tipo)"
                ),
                {
                    "id": _listed_asset_pk(str(r["tipo"]), str(r["codigo"])),
                    "codigo": str(r["codigo"])[:32],
                    "nome": str(r["nome"])[:200],
                    "tipo": str(r["tipo"])[:20],
                },
            )


def _ensure_user_username_account_status_sqlite(engine: Engine) -> None:
    """Colunas username/account_status em SQLite legado — sem gerar username a partir do e-mail."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("users"):
        return
    ucols = {c["name"] for c in insp.get_columns("users")}
    if "username" not in ucols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(64)"))
    if "account_status" not in ucols:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN account_status VARCHAR(16) NOT NULL DEFAULT 'active'"
                )
            )

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET account_status = 'active' "
                "WHERE account_status IS NULL OR account_status = ''"
            )
        )
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_users_account_status ON users (account_status)")
        )

    ucols = {c["name"] for c in inspect(engine).get_columns("users")}
    if "goal_pool_withdrawn_to_income" not in ucols:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN goal_pool_withdrawn_to_income "
                    "NUMERIC(14, 2) NOT NULL DEFAULT 0"
                )
            )


def _ensure_investment_fii_columns_sqlite(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("investments"):
        return
    cols = {c["name"] for c in insp.get_columns("investments")}
    with engine.begin() as conn:
        if "quantidade" not in cols:
            conn.execute(text("ALTER TABLE investments ADD COLUMN quantidade NUMERIC(18, 8)"))
        if "preco_medio" not in cols:
            conn.execute(text("ALTER TABLE investments ADD COLUMN preco_medio NUMERIC(14, 6)"))
        if "preco_unitario_atual" not in cols:
            conn.execute(text("ALTER TABLE investments ADD COLUMN preco_unitario_atual NUMERIC(14, 6)"))


def _repair_orphan_goal_transaction_income_links(engine: Engine) -> None:
    """Remove vínculos income_id apontando para receitas já excluídas."""
    insp = inspect(engine)
    if not insp.has_table("goal_transactions") or not insp.has_table("incomes"):
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE goal_transactions
                SET income_id = NULL
                WHERE income_id IS NOT NULL
                  AND income_id NOT IN (SELECT id FROM incomes)
                """
            )
        )


def _ensure_goal_transaction_income_id_sqlite(engine: Engine) -> None:
    """Coluna `income_id` da migração Alembic `k7l8m9n0o1p2` para SQLite legado."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("goal_transactions"):
        return
    cols = {c["name"] for c in insp.get_columns("goal_transactions")}
    if "income_id" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE goal_transactions ADD COLUMN income_id TEXT "
                "REFERENCES incomes(id) ON DELETE SET NULL"
            )
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_goal_transactions_income_id ON goal_transactions (income_id)")
        )


def _ensure_goal_transaction_period_id_sqlite(engine: Engine) -> None:
    """Coluna `period_id` da migração Alembic `s5t6u7v8w9x0` para SQLite legado."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("goal_transactions"):
        return
    cols = {c["name"] for c in insp.get_columns("goal_transactions")}
    if "period_id" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE goal_transactions ADD COLUMN period_id TEXT "
                "REFERENCES periods(id) ON DELETE SET NULL"
            )
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_goal_transactions_period_id ON goal_transactions (period_id)")
        )


def _ensure_income_origem_meta_sqlite(engine: Engine) -> None:
    """Coluna `origem_meta` da migração Alembic `s5t6u7v8w9x0` para SQLite legado."""
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if not insp.has_table("incomes"):
        return
    cols = {c["name"] for c in insp.get_columns("incomes")}
    if "origem_meta" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE incomes ADD COLUMN origem_meta BOOLEAN NOT NULL DEFAULT 0"))


def apply_sqlite_schema_patches(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if insp.has_table("expenses"):
        cols = {c["name"] for c in insp.get_columns("expenses")}
        if "recorrente" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE expenses ADD COLUMN recorrente BOOLEAN NOT NULL DEFAULT 0"))

    if insp.has_table("card_transactions"):
        ct_cols = {c["name"] for c in insp.get_columns("card_transactions")}
        if "data" not in ct_cols or "pago" not in ct_cols:
            with engine.begin() as conn:
                if "data" not in ct_cols:
                    conn.execute(text("ALTER TABLE card_transactions ADD COLUMN data DATE"))
                if "pago" not in ct_cols:
                    conn.execute(text("ALTER TABLE card_transactions ADD COLUMN pago BOOLEAN"))
                conn.execute(
                    text("UPDATE card_transactions SET data = date(created_at) WHERE data IS NULL")
                )
                conn.execute(text("UPDATE card_transactions SET pago = 1 WHERE pago IS NULL"))
        if "from_statement" not in ct_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE card_transactions ADD COLUMN from_statement BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
        if "installment_group_id" not in ct_cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE card_transactions ADD COLUMN installment_group_id TEXT")
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_card_transactions_installment_group_id "
                        "ON card_transactions (installment_group_id)"
                    )
                )

    if not insp.has_table("spenders"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE spenders (
                        id TEXT NOT NULL PRIMARY KEY,
                        nome VARCHAR(200) NOT NULL,
                        is_global BOOLEAN NOT NULL DEFAULT 1,
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_spenders_user_id ON spenders (user_id)"))
            conn.execute(text("CREATE INDEX ix_spenders_is_global ON spenders (is_global)"))
    elif insp.has_table("spenders"):
        scols = {c["name"] for c in insp.get_columns("spenders")}
        if "is_global" not in scols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE spenders ADD COLUMN is_global BOOLEAN NOT NULL DEFAULT 1"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_spenders_is_global ON spenders (is_global)"))

    if insp.has_table("card_transactions") and not insp.has_table("card_transaction_shares"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE card_transaction_shares (
                        id TEXT NOT NULL PRIMARY KEY,
                        valor NUMERIC(14, 2) NOT NULL,
                        pago BOOLEAN NOT NULL DEFAULT 0,
                        card_transaction_id TEXT NOT NULL REFERENCES card_transactions(id) ON DELETE CASCADE,
                        spender_id TEXT NOT NULL REFERENCES spenders(id) ON DELETE RESTRICT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX ix_card_transaction_shares_card_transaction_id ON card_transaction_shares (card_transaction_id)"
                )
            )
            conn.execute(
                text("CREATE INDEX ix_card_transaction_shares_spender_id ON card_transaction_shares (spender_id)")
            )

    if insp.has_table("card_transaction_shares"):
        cts_cols = {c["name"] for c in insp.get_columns("card_transaction_shares")}
        if "pago" not in cts_cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE card_transaction_shares ADD COLUMN pago BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
                conn.execute(
                    text(
                        """
                        UPDATE card_transaction_shares
                        SET pago = 1
                        WHERE card_transaction_id IN (
                            SELECT id FROM card_transactions WHERE pago = 1
                        )
                        """
                    )
                )

    if insp.has_table("expenses") and insp.has_table("spenders") and not insp.has_table("expense_shares"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE expense_shares (
                        id TEXT NOT NULL PRIMARY KEY,
                        valor NUMERIC(14, 2) NOT NULL,
                        pago BOOLEAN NOT NULL DEFAULT 0,
                        expense_id TEXT NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
                        spender_id TEXT NOT NULL REFERENCES spenders(id) ON DELETE RESTRICT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_expense_shares_expense_id ON expense_shares (expense_id)"))
            conn.execute(text("CREATE INDEX ix_expense_shares_spender_id ON expense_shares (spender_id)"))

    if insp.has_table("expense_shares"):
        es_cols = {c["name"] for c in insp.get_columns("expense_shares")}
        if "pago" not in es_cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE expense_shares ADD COLUMN pago BOOLEAN NOT NULL DEFAULT 0")
                )
                conn.execute(
                    text(
                        """
                        UPDATE expense_shares
                        SET pago = 1
                        WHERE expense_id IN (SELECT id FROM expenses WHERE pago = 1)
                        """
                    )
                )

    _ensure_user_username_account_status_sqlite(engine)

    if insp.has_table("users"):
        ucols = {c["name"] for c in insp.get_columns("users")}
        if "me_spender_id" not in ucols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN me_spender_id TEXT "
                        "REFERENCES spenders(id) ON DELETE SET NULL"
                    )
                )
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_me_spender_id ON users (me_spender_id)"))
        if "is_admin" not in ucols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_admin ON users (is_admin)"))
        if "must_change_password" not in ucols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 0")
                )
        if "avatar_bytes" not in ucols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_bytes BLOB"))
        if "avatar_content_type" not in ucols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_content_type VARCHAR(64)"))

    if insp.has_table("cards") and not insp.has_table("card_split_templates"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE card_split_templates (
                        id TEXT NOT NULL PRIMARY KEY,
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                        description_key VARCHAR(500) NOT NULL,
                        parts JSON NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                        UNIQUE (user_id, card_id, description_key)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_card_split_templates_user_id ON card_split_templates (user_id)"))
            conn.execute(text("CREATE INDEX ix_card_split_templates_card_id ON card_split_templates (card_id)"))

    if not insp.has_table("debtor_loans"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE debtor_loans (
                        id TEXT NOT NULL PRIMARY KEY,
                        devedor_nome VARCHAR(200) NOT NULL,
                        valor_emprestado NUMERIC(14, 2) NOT NULL,
                        data_emprestimo DATE NOT NULL,
                        destino_dinheiro VARCHAR(500) NOT NULL,
                        observacoes TEXT,
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        spender_id TEXT REFERENCES spenders(id) ON DELETE SET NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_debtor_loans_user_id ON debtor_loans (user_id)"))
            conn.execute(text("CREATE INDEX ix_debtor_loans_spender_id ON debtor_loans (spender_id)"))
            conn.execute(
                text("CREATE INDEX ix_debtor_loans_data_emprestimo ON debtor_loans (data_emprestimo)")
            )
    elif insp.has_table("debtor_loans"):
        dcols = {c["name"] for c in insp.get_columns("debtor_loans")}
        if "spender_id" not in dcols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE debtor_loans ADD COLUMN spender_id TEXT "
                        "REFERENCES spenders(id) ON DELETE SET NULL"
                    )
                )
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_debtor_loans_spender_id ON debtor_loans (spender_id)"))

    if not insp.has_table("debtor_payments"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE debtor_payments (
                        id TEXT NOT NULL PRIMARY KEY,
                        data_pagamento DATE NOT NULL,
                        valor_pago NUMERIC(14, 2) NOT NULL,
                        observacao VARCHAR(500),
                        emprestimo_id TEXT NOT NULL REFERENCES debtor_loans(id) ON DELETE CASCADE,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_debtor_payments_emprestimo_id ON debtor_payments (emprestimo_id)"))
            conn.execute(
                text("CREATE INDEX ix_debtor_payments_data_pagamento ON debtor_payments (data_pagamento)")
            )

    if not insp.has_table("trips"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE trips (
                        id TEXT NOT NULL PRIMARY KEY,
                        nome VARCHAR(200) NOT NULL,
                        destino VARCHAR(200),
                        data_inicio DATE,
                        data_fim DATE,
                        moeda_base VARCHAR(8) NOT NULL DEFAULT 'BRL',
                        orcamento_total NUMERIC(14, 2),
                        status VARCHAR(20) NOT NULL DEFAULT 'planning',
                        observacoes TEXT,
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_trips_user_id ON trips (user_id)"))

    if not insp.has_table("trip_participants"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE trip_participants (
                        id TEXT NOT NULL PRIMARY KEY,
                        trip_id TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                        spender_id TEXT NOT NULL REFERENCES spenders(id) ON DELETE RESTRICT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                        CONSTRAINT uq_trip_participant UNIQUE (trip_id, spender_id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_trip_participants_trip_id ON trip_participants (trip_id)"))
            conn.execute(
                text("CREATE INDEX ix_trip_participants_spender_id ON trip_participants (spender_id)")
            )

    if not insp.has_table("trip_expenses"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE trip_expenses (
                        id TEXT NOT NULL PRIMARY KEY,
                        descricao VARCHAR(500) NOT NULL,
                        valor NUMERIC(14, 2) NOT NULL,
                        moeda VARCHAR(8) NOT NULL DEFAULT 'BRL',
                        taxa_cambio NUMERIC(14, 6),
                        valor_base NUMERIC(14, 2) NOT NULL,
                        data DATE NOT NULL,
                        categoria VARCHAR(20) NOT NULL,
                        forma_pagamento VARCHAR(20) NOT NULL DEFAULT 'cash',
                        observacao TEXT,
                        trip_id TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        paid_by_spender_id TEXT NOT NULL REFERENCES spenders(id) ON DELETE RESTRICT,
                        pushed_expense_id TEXT REFERENCES expenses(id) ON DELETE SET NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_trip_expenses_trip_id ON trip_expenses (trip_id)"))
            conn.execute(text("CREATE INDEX ix_trip_expenses_user_id ON trip_expenses (user_id)"))
            conn.execute(
                text("CREATE INDEX ix_trip_expenses_paid_by_spender_id ON trip_expenses (paid_by_spender_id)")
            )
            conn.execute(
                text("CREATE INDEX ix_trip_expenses_pushed_expense_id ON trip_expenses (pushed_expense_id)")
            )

    if not insp.has_table("trip_expense_shares"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE trip_expense_shares (
                        id TEXT NOT NULL PRIMARY KEY,
                        valor NUMERIC(14, 2) NOT NULL,
                        trip_expense_id TEXT NOT NULL REFERENCES trip_expenses(id) ON DELETE CASCADE,
                        spender_id TEXT NOT NULL REFERENCES spenders(id) ON DELETE RESTRICT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX ix_trip_expense_shares_trip_expense_id ON trip_expense_shares (trip_expense_id)")
            )
            conn.execute(
                text("CREATE INDEX ix_trip_expense_shares_spender_id ON trip_expense_shares (spender_id)")
            )

    if insp.has_table("users"):
        ucols = {c["name"] for c in insp.get_columns("users")}
        if "login_count" not in ucols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN login_count INTEGER NOT NULL DEFAULT 0"))
        if "last_login_at" not in ucols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at TEXT"))
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_users_last_login_at ON users (last_login_at)")
                )
        if "notifications_generated_at" not in ucols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN notifications_generated_at TEXT"))

    if not insp.has_table("system_error_logs"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE system_error_logs (
                        id TEXT NOT NULL PRIMARY KEY,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        method VARCHAR(16) NOT NULL,
                        path VARCHAR(512) NOT NULL,
                        status_code INTEGER NOT NULL,
                        detail TEXT,
                        traceback TEXT,
                        user_id TEXT
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_system_error_logs_created_at ON system_error_logs (created_at)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_system_error_logs_status_code ON system_error_logs (status_code)")
            )

    if not insp.has_table("user_access_logs"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE user_access_logs (
                        id TEXT NOT NULL PRIMARY KEY,
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        event_type VARCHAR(32) NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_user_access_logs_user_id ON user_access_logs (user_id)")
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_user_access_logs_created_at ON user_access_logs (created_at)"
                )
            )

    if not insp.has_table("notifications"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE notifications (
                        id TEXT NOT NULL PRIMARY KEY,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        modulo VARCHAR(40) NOT NULL,
                        tipo VARCHAR(80) NOT NULL,
                        severidade VARCHAR(20) NOT NULL,
                        titulo VARCHAR(300) NOT NULL,
                        subtitulo VARCHAR(500) NOT NULL DEFAULT '',
                        lida BOOLEAN NOT NULL DEFAULT 0,
                        link VARCHAR(300) NOT NULL DEFAULT '',
                        referencia_id VARCHAR(64) NOT NULL,
                        lida_em TEXT
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id)")
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_notifications_user_tipo_ref_lida "
                    "ON notifications (user_id, tipo, referencia_id, lida)"
                )
            )

    _ensure_investment_fii_columns_sqlite(engine)
    _ensure_goal_transaction_income_id_sqlite(engine)
    _ensure_goal_transaction_period_id_sqlite(engine)
    _ensure_income_origem_meta_sqlite(engine)
    _repair_orphan_goal_transaction_income_links(engine)
    _ensure_listed_assets_sqlite(engine)
    ensure_platform_settings(engine)


def repair_goal_pool_data_consistency(engine: Engine) -> None:
    """Corrige vínculos órfãos e garante competência mensal nas movimentações de metas."""
    _repair_orphan_goal_transaction_income_links(engine)
    backfill_goal_period_competence(engine)


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def backfill_goal_period_competence(engine: Engine) -> None:
    """Atribui período às movimentações antigas e marca receitas vindas de retirada de meta.

    Idempotente: só toca em linhas ainda sem competência, então cobre tanto o banco legado
    quanto movimentações cujo período só foi criado depois.
    """
    insp = inspect(engine)
    if not insp.has_table("goal_transactions") or not insp.has_table("periods"):
        return
    gt_cols = {c["name"] for c in insp.get_columns("goal_transactions")}
    if "period_id" not in gt_cols:
        return

    with engine.begin() as conn:
        pending = conn.execute(
            text("SELECT id, user_id, data FROM goal_transactions WHERE period_id IS NULL")
        ).fetchall()
        if pending:
            periods = {
                (str(user_id), int(ano), int(mes)): period_id
                for period_id, user_id, mes, ano in conn.execute(
                    text("SELECT id, user_id, mes, ano FROM periods")
                )
            }
            for tx_id, user_id, data in pending:
                parsed = _as_date(data)
                if parsed is None:
                    continue
                period_id = periods.get((str(user_id), parsed.year, parsed.month))
                if period_id is None:
                    continue
                conn.execute(
                    text("UPDATE goal_transactions SET period_id = :period_id WHERE id = :tx_id"),
                    {"period_id": period_id, "tx_id": tx_id},
                )

    if "origem_meta" not in {c["name"] for c in insp.get_columns("incomes")}:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE incomes
                SET origem_meta = :truthy
                WHERE origem_meta = :falsy
                  AND id IN (SELECT income_id FROM goal_transactions WHERE income_id IS NOT NULL)
                """
            ),
            {"truthy": True, "falsy": False},
        )


def ensure_platform_settings(engine: Engine) -> None:
    """Garante valores padrão de sessão. Em PostgreSQL o schema vem do Alembic."""
    insp = inspect(engine)
    if not insp.has_table("platform_settings"):
        if engine.dialect.name == "postgresql":
            return
        from app.models.platform_setting import PlatformSetting

        PlatformSetting.__table__.create(bind=engine)

    if engine.dialect.name == "sqlite":
        insert_sql = "INSERT OR IGNORE INTO platform_settings (key, value) VALUES (:key, :value)"
    else:
        insert_sql = (
            "INSERT INTO platform_settings (key, value) VALUES (:key, :value) "
            "ON CONFLICT (key) DO NOTHING"
        )

    seeds = [
        ("inactivity_logout_minutes", "60"),
        ("inactivity_logout_enabled", "1"),
    ]
    with engine.begin() as conn:
        for key, value in seeds:
            conn.execute(text(insert_sql), {"key": key, "value": value})
