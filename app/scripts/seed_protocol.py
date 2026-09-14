"""Seed dos templates de protocolo por especialidade (idempotente).

Cada pacote clínico (psiquiatria, psicologia…) tem um template global (tenant_id
nulo) que os médicos clonam. Semear todos mantém o registry e o banco em sincronia.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clinical.packs import CLINICAL_PACKS, PSYCHIATRY_PACK, ClinicalPack
from app.db.session import AsyncSessionLocal
from app.models.protocol import Protocol, ProtocolQuestion


async def seed_pack_protocol(session: AsyncSession, pack: ClinicalPack) -> Protocol:
    """Cria o template global do pacote, se ainda não existir."""
    existing = await session.execute(
        select(Protocol).where(
            Protocol.tenant_id.is_(None),  # só o template global (não as cópias dos médicos)
            Protocol.specialty == pack.specialty,
            Protocol.version == pack.protocol_version,
        )
    )
    protocol = existing.scalar_one_or_none()
    if protocol is not None:
        return protocol

    protocol = Protocol(
        name=pack.protocol_name,
        specialty=pack.specialty,
        version=pack.protocol_version,
        description=pack.protocol_description,
        is_active=True,
    )
    session.add(protocol)
    await session.flush()

    for q in pack.questions:
        session.add(
            ProtocolQuestion(
                protocol_id=protocol.id,
                code=q.code,
                category=q.category,
                text=q.text,
                type=q.type,
                position=q.position,
                required=q.required,
                options=q.options,
            )
        )
    await session.flush()
    return protocol


async def seed_psychiatry_protocol(session: AsyncSession) -> Protocol:
    """Compat: semeia o template de psiquiatria (usado por testes e seed antigo)."""
    return await seed_pack_protocol(session, PSYCHIATRY_PACK)


async def seed_all_packs(session: AsyncSession) -> list[Protocol]:
    """Semeia o template de todos os pacotes registrados."""
    return [await seed_pack_protocol(session, pack) for pack in CLINICAL_PACKS.values()]


async def main() -> None:
    async with AsyncSessionLocal() as session:
        protocols = await seed_all_packs(session)
        await session.commit()
        for p in protocols:
            print(f"Protocolo pronto: {p.name} v{p.version} ({p.id})")


if __name__ == "__main__":
    asyncio.run(main())
