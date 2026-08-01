"""Job de lembretes de consulta (para agendar via cron/scheduler).

Avisa os pacientes das consultas dentro da janela de antecedência. Idempotente.

Uso: python -m app.scripts.scan_appointments
"""

from __future__ import annotations

import asyncio

from app.db.session import AsyncSessionLocal
from app.services.appointment_service import scan_appointment_reminders


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await scan_appointment_reminders(session)
        await session.commit()
        print(f"Lembretes de consulta enviados: {result['reminders']}")


if __name__ == "__main__":
    asyncio.run(main())
