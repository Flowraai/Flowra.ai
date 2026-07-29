"""Seed do protocolo psiquiátrico pré-definido do MVP (idempotente)."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.protocol import Protocol, ProtocolQuestion
from app.protocol import psychiatry as P


async def seed_psychiatry_protocol(session: AsyncSession) -> Protocol:
    existing = await session.execute(
        select(Protocol).where(
            Protocol.specialty == P.PSYCHIATRY_SPECIALTY,
            Protocol.version == P.PSYCHIATRY_PROTOCOL_VERSION,
        )
    )
    protocol = existing.scalar_one_or_none()
    if protocol is not None:
        return protocol

    protocol = Protocol(
        name=P.PSYCHIATRY_PROTOCOL_NAME,
        specialty=P.PSYCHIATRY_SPECIALTY,
        version=P.PSYCHIATRY_PROTOCOL_VERSION,
        description="Protocolo diário de acompanhamento psiquiátrico (MVP).",
        is_active=True,
    )
    session.add(protocol)
    await session.flush()

    for q in P.PSYCHIATRY_QUESTIONS:
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


async def main() -> None:
    async with AsyncSessionLocal() as session:
        protocol = await seed_psychiatry_protocol(session)
        await session.commit()
        print(f"Protocolo pronto: {protocol.name} v{protocol.version} ({protocol.id})")


if __name__ == "__main__":
    asyncio.run(main())
