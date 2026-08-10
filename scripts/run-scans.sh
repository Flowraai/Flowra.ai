#!/bin/sh
# Roda os scans agendados do Flowra Care dentro do container `api`.
# (host da VPS, a partir da raiz do repo)
#
# CL-4 — sem isto, os alertas de inatividade, não-adesão à medicação e os
# lembretes de consulta NUNCA rodam. Cada scan é idempotente; a falha de um
# não impede os outros.
#
# Uso:   ./scripts/run-scans.sh
# Cron:  */15 * * * *  cd /opt/flowra && ./scripts/run-scans.sh >> /var/log/flowra-scans.log 2>&1
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
# Heartbeat: última execução em que TODOS os scans terminaram OK. Um monitor
# externo (check-scans-heartbeat.sh) avisa se este arquivo ficar velho.
HEARTBEAT_FILE="${HEARTBEAT_FILE:-/var/log/flowra-scans.heartbeat}"

run() {
	echo "[scans] $(date -u +%Y-%m-%dT%H:%M:%SZ) rodando $1"
	docker compose -f "$COMPOSE_FILE" exec -T api python -m "$1"
}

rc=0
run app.scripts.scan_medications  || rc=1
run app.scripts.scan_appointments || rc=1
run app.scripts.scan_inactivity   || rc=1

if [ "$rc" -eq 0 ]; then
	date -u +%Y-%m-%dT%H:%M:%SZ >"$HEARTBEAT_FILE"
	echo "[scans] ok"
else
	# Saída não-vazia + exit!=0: o cron manda o log ao MAILTO (se configurado).
	echo "[scans] ALGUM SCAN FALHOU (rc=$rc) — verifique $COMPOSE_FILE e o container api"
fi
exit "$rc"
