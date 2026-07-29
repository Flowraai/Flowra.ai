"""Rotas de protocolo (leitura). O protocolo psiquiátrico do MVP é fixo (seed)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.protocol import Protocol
from app.schemas.protocol import ProtocolRead

router = APIRouter(prefix="/protocols", tags=["protocols"])


@router.get("/active", response_model=ProtocolRead)
async def active_protocol(
    _: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Protocol:
    result = await session.execute(
        select(Protocol)
        .where(Protocol.specialty == "psiquiatria", Protocol.is_active.is_(True))
        .options(selectinload(Protocol.questions))
        .order_by(Protocol.created_at.desc())
    )
    protocol = result.scalars().first()
    if protocol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum protocolo psiquiátrico ativo. Rode o seed do protocolo.",
        )
    return protocol
