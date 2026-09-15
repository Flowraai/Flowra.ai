#!/usr/bin/env bash
# Deploy do Flowra Care na VPS: backup -> atualizar código -> compose up -> verificar.
#
# Uso (na própria VPS):
#   ./deploy/vps-deploy.sh docker-compose.prod.yml claude/mvp-psiquiatria-backend-7hoako
#
# É também o que o GitHub Actions executa por SSH:
#   ssh ... "DEPLOY_PATH=/opt/flowra bash -s -- <compose_file> <ref>" < deploy/vps-deploy.sh
#
# Idempotente e seguro para rodar de novo. NÃO toca no .env (fica fora do git).
set -euo pipefail

COMPOSE_FILE="${1:-docker-compose.prod.yml}"
REF="${2:-}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/flowra}"

cd "$DEPLOY_PATH"

echo "== Backup do banco (antes de qualquer migração) =="
if [ -x ./scripts/backup-db.sh ]; then
  ./scripts/backup-db.sh
else
  echo "AVISO: scripts/backup-db.sh ausente/não executável — pulando backup" >&2
fi

echo "== Atualizando o código =="
git fetch --all --prune
if [ -n "$REF" ]; then
  git checkout "$REF"
  # A VPS é um espelho do origin: descarta divergências locais na árvore versionada
  # (o .env e os volumes/backups ficam fora do git e não são afetados).
  git reset --hard "origin/$REF"
fi
echo "HEAD agora em: $(git rev-parse --short HEAD) ($(git rev-parse --abbrev-ref HEAD))"

echo "== Subindo os containers ($COMPOSE_FILE) — migrações rodam no boot =="
docker compose -f "$COMPOSE_FILE" up -d --build

echo "== Aguardando a API ficar pronta (readiness + banco) =="
ok=0
for _ in $(seq 1 45); do
  if docker compose -f "$COMPOSE_FILE" exec -T api \
      python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready').status==200 else 1)" 2>/dev/null; then
    ok=1; break
  fi
  sleep 2
done
if [ "$ok" != 1 ]; then
  echo "ERRO: a API não ficou pronta a tempo — últimos logs:" >&2
  docker compose -f "$COMPOSE_FILE" logs --tail=80 api >&2 || true
  exit 1
fi

echo "== Migração aplicada (alembic current) =="
docker compose -f "$COMPOSE_FILE" exec -T api alembic current

echo "== Estado dos serviços =="
docker compose -f "$COMPOSE_FILE" ps

echo "== Deploy concluído com sucesso =="
