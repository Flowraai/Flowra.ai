#!/bin/sh
# Backup do Postgres de produção (roda no host da VPS, a partir da raiz do repo).
# Faz pg_dump dentro do container db e grava um .sql.gz com rotação.
#
# Uso:   ./scripts/backup-db.sh
# Cron:  0 3 * * *  cd /opt/flowra && ./scripts/backup-db.sh >> /var/log/flowra-backup.log 2>&1
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP="${KEEP:-14}" # quantos backups manter
PG_USER="${POSTGRES_USER:-flowra}"
PG_DB="${POSTGRES_DB:-flowra_care}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/flowra-$STAMP.sql.gz"

echo "[backup] gerando $OUT"
docker compose -f "$COMPOSE_FILE" exec -T db \
	pg_dump -U "$PG_USER" -d "$PG_DB" --clean --if-exists | gzip -9 >"$OUT"

# Rotação: mantém apenas os KEEP mais recentes.
ls -1t "$BACKUP_DIR"/flowra-*.sql.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
	echo "[backup] removendo antigo $old"
	rm -f "$old"
done

echo "[backup] ok — $(ls -1 "$BACKUP_DIR"/flowra-*.sql.gz 2>/dev/null | wc -l) backup(s)."
echo "[backup] GUARDE cópias fora da VPS e proteja também a ENCRYPTION_KEY (sem ela, os campos cifrados no dump são ilegíveis)."
