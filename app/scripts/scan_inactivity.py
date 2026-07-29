"""Job de varredura de não-adesão (para agendar via cron/scheduler).

Gera alertas para todos os pacientes ativos sem check-in recente. Idempotente.

Uso: python -m app.scripts.scan_inactivity
"""

from __future__ import annotations

import asyncio

from app.db.session import AsyncSessionLocal
from app.services.inactivity_service import scan_inactivity


async def main() -> None:
    async with AsyncSessionLocal() as session:
        created = await scan_inactivity(session)
        await session.commit()
        print(f"Alertas de inatividade criados: {len(created)}")


if __name__ == "__main__":
    asyncio.run(main())
