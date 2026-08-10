#!/bin/sh
# Monitor do heartbeat dos scans (CL-4): avisa se os scans agendados pararam.
# (host da VPS, a partir da raiz do repo)
#
# Sai com erro e imprime uma mensagem se o heartbeat estiver mais velho que
# MAX_AGE_MIN minutos (ou se nunca tiver rodado). Rode por cron: qualquer saída
# não-vazia é enviada ao MAILTO configurado no crontab — o padrão de alerta do cron.
#
# Uso:   ./scripts/check-scans-heartbeat.sh
# Cron:  17 * * * *  cd /opt/flowra && ./scripts/check-scans-heartbeat.sh >> /var/log/flowra-scans.log 2>&1
set -eu

HEARTBEAT_FILE="${HEARTBEAT_FILE:-/var/log/flowra-scans.heartbeat}"
# Folga generosa sobre o intervalo de 15 min do run-scans.sh (default 45 min).
MAX_AGE_MIN="${MAX_AGE_MIN:-45}"

if [ ! -f "$HEARTBEAT_FILE" ]; then
	echo "[scans-monitor] ALERTA: heartbeat inexistente ($HEARTBEAT_FILE) — os scans nunca rodaram com sucesso."
	exit 1
fi

now=$(date -u +%s)
mtime=$(date -u -r "$HEARTBEAT_FILE" +%s)
age_min=$(( (now - mtime) / 60 ))

if [ "$age_min" -gt "$MAX_AGE_MIN" ]; then
	echo "[scans-monitor] ALERTA: scans parados há ${age_min} min (limite ${MAX_AGE_MIN} min). Último OK: $(cat "$HEARTBEAT_FILE")."
	exit 1
fi

echo "[scans-monitor] ok — último scan há ${age_min} min."
