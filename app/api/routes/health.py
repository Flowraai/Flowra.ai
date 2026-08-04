"""Health checks (liveness/readiness) para orquestradores e balanceadores."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])
logger = logging.getLogger("flowra_care.health")


@router.get("/health")
async def health() -> dict:
    """Info básica da aplicação (não toca no banco)."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@router.get("/health/live")
async def liveness() -> dict:
    """Liveness: o processo está de pé. Nunca depende de serviços externos —
    falhar aqui deve reiniciar o container, não é o caso quando o banco cai."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(response: Response, session: AsyncSession = Depends(get_db)) -> dict:
    """Readiness: pronto para receber tráfego (verifica o banco). Retorna 503 se o
    banco estiver inacessível — o orquestrador tira a instância do balanceador."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.error("readiness_failed: %s", exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "unreachable"}
    return {"status": "ready", "database": "reachable"}


@router.get("/health/db")
async def health_db(response: Response, session: AsyncSession = Depends(get_db)) -> dict:
    """Compatibilidade: alias de readiness restrito ao banco."""
    return await readiness(response, session)
