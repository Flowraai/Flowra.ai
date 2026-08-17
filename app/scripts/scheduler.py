"""Agendador do Flowra Care (worker separado).

Roda as varreduras periódicas que fazem o produto funcionar sozinho:
- lembretes de medicação (e marca doses vencidas como não tomadas + alerta de faltas);
- lembretes de consulta;
- alertas de inatividade (paciente que parou de responder).

Cada varredura é **idempotente** (dedup por reminded_at / reminder_sent_at /
alerta em aberto) e **isolada**: uma falha é logada e não derruba as outras nem
o loop. A entrega usa os canais configurados (log/e-mail/WhatsApp/push).

Sobe como um processo à parte:  python -m app.scripts.scheduler
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.services.appointment_service import scan_appointment_reminders
from app.services.inactivity_service import scan_inactivity
from app.services.medication_service import scan_due_medications

logger = logging.getLogger("flowra_care.scheduler")


async def _run_scan(name: str, fn) -> None:
    try:
        async with AsyncSessionLocal() as session:
            result = await fn(session)
            await session.commit()
        summary = len(result) if isinstance(result, list) else result
        logger.info("varredura ok", extra={"scan": name, "result": summary})
    except Exception:  # noqa: BLE001 — uma varredura não pode derrubar as outras
        logger.exception("varredura falhou", extra={"scan": name})


async def run_once() -> None:
    await _run_scan("medicacao", scan_due_medications)
    await _run_scan("consultas", scan_appointment_reminders)
    await _run_scan("inatividade", scan_inactivity)


async def main() -> None:
    setup_logging()
    interval = max(settings.scheduler_interval_seconds, 30)
    logger.info("agendador iniciado", extra={"interval_s": interval})
    while True:
        await run_once()
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
