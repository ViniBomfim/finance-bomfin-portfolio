#!/bin/sh
# Entrypoint no Render (Docker): migrações + Uvicorn na porta $PORT.
set -e

on_error() {
  echo "[render-start] ERRO: comando falhou (exit $?)." >&2
  echo "[render-start] Verifique DATABASE_URL, Alembic e logs acima." >&2
}
trap on_error EXIT

echo "[render-start] BomFin API — iniciando container..."
echo "[render-start] Aplicando migrações Alembic..."
alembic upgrade head
echo "[render-start] Migrações Alembic OK."

PORT="${PORT:-8000}"
echo "[render-start] Subindo API em 0.0.0.0:${PORT}"
trap - EXIT
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
