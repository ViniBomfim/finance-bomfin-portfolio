"""Aplica migrações Alembic (PostgreSQL / Supabase em produção)."""

from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)


def run_alembic_upgrade(revision: str = "head") -> None:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, revision)
    out = StringIO()
    command.current(cfg, verbose=False, output=out)
    current = out.getvalue().strip() or revision
    logger.info("Migrações Alembic concluídas. Revisão atual: %s", current)
