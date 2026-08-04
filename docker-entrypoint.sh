#!/bin/sh
# Entrypoint de produção: aplica migrações (e seed opcional) antes de subir a API.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] Aplicando migrações (alembic upgrade head)..."
  alembic upgrade head
fi

if [ "${SEED_PROTOCOL:-false}" = "true" ]; then
  echo "[entrypoint] Populando o protocolo psiquiátrico (idempotente)..."
  python -m app.scripts.seed_protocol
fi

echo "[entrypoint] Iniciando: $*"
exec "$@"
