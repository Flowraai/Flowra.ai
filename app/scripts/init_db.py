"""Bootstrap de desenvolvimento: cria as tabelas e roda o seed do protocolo.

Para produção, prefira migrações Alembic (ver alembic/ e README).
"""

from __future__ import annotations

import asyncio

from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models import *  # noqa: F401,F403  (registra o metadata das tabelas)
from app.scripts.seed_protocol import seed_psychiatry_protocol


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_psychiatry_protocol(session)
        await session.commit()

    print("Banco inicializado e protocolo psiquiátrico populado.")


if __name__ == "__main__":
    asyncio.run(main())
