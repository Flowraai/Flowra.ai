"""Job de agendamento de medicação (para agendar via cron/scheduler).

Cria as doses que venceram, envia lembretes e marca as pendentes de dias
anteriores como 'não tomou'. Idempotente.

Uso: python -m app.scripts.scan_medications
"""

from __future__ import annotations

import asyncio

from app.db.session import AsyncSessionLocal
from app.services.medication_service import scan_due_medications


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await scan_due_medications(session)
        await session.commit()
        print(
            f"Lembretes enviados: {result['reminders']} | "
            f"doses marcadas como não tomadas: {result['marked_missed']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
