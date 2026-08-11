"""listed_assets catalog + investments.listed_asset_id

Revision ID: b1c2d3e4f5a0
Revises: a9b8c7d6e5f4
Create Date: 2026-05-09

"""
import json
import uuid
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a0"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FM_NS = uuid.UUID("019b0000-0000-7000-8000-000000000001")


def _listed_asset_uuid(tipo: str, codigo: str) -> str:
    return str(uuid.uuid5(_FM_NS, f"{tipo}:{codigo.upper()}"))


def upgrade() -> None:
    op.create_table(
        "listed_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("codigo", sa.String(length=32), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_listed_assets_codigo"), "listed_assets", ["codigo"], unique=True)
    op.create_index(op.f("ix_listed_assets_tipo"), "listed_assets", ["tipo"], unique=False)

    root = Path(__file__).resolve().parents[2]
    seed_path = root / "app" / "data" / "listed_assets_seed.json"
    with open(seed_path, encoding="utf-8") as f:
        seed = json.load(f)
    rows = [
        {
            "id": uuid.UUID(_listed_asset_uuid(r["tipo"], r["codigo"])),
            "codigo": str(r["codigo"])[:32],
            "nome": str(r["nome"])[:200],
            "tipo": str(r["tipo"])[:20],
        }
        for r in seed
    ]
    listed_assets_table = sa.table(
        "listed_assets",
        sa.column("id", sa.Uuid()),
        sa.column("codigo", sa.String()),
        sa.column("nome", sa.String()),
        sa.column("tipo", sa.String()),
    )
    op.bulk_insert(listed_assets_table, rows)

    op.add_column("investments", sa.Column("listed_asset_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_investments_listed_asset_id"), "investments", ["listed_asset_id"], unique=False)
    # SQLite não suporta ALTER ADD CONSTRAINT; integridade fica a cargo do ORM em dev.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_investments_listed_asset_id_listed_assets",
            "investments",
            "listed_assets",
            ["listed_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_investments_listed_asset_id_listed_assets",
            "investments",
            type_="foreignkey",
        )
    op.drop_index(op.f("ix_investments_listed_asset_id"), table_name="investments")
    op.drop_column("investments", "listed_asset_id")
    op.drop_index(op.f("ix_listed_assets_tipo"), table_name="listed_assets")
    op.drop_index(op.f("ix_listed_assets_codigo"), table_name="listed_assets")
    op.drop_table("listed_assets")
