"""Webhook da Evolution: recebe as respostas do paciente no WhatsApp.

Endpoint público (a Evolution chama), autenticado por um token na URL
(/webhooks/evolution/{token}), comparado com EVOLUTION_WEBHOOK_TOKEN. Sem o token
configurado, o webhook fica desligado (404) — nunca aceita chamada não verificada.

Responde sempre 200 para a Evolution não reenfileirar: erros de processamento são
tratados como "ignorado".
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services import whatsapp_inbound_service as inbound

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger("flowra_care.whatsapp_inbound")


@router.post("/webhooks/evolution/{token}")
async def evolution_webhook(
    token: str, request: Request, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    expected = settings.evolution_webhook_token
    if not expected or token != expected:
        # Sem token configurado (desligado) ou token errado: some, sem detalhes.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 — corpo inválido: ignora
        return {"status": "ignored"}

    msg = inbound.parse_event(payload if isinstance(payload, dict) else {})
    if msg is None:
        return {"status": "ignored"}

    try:
        action = await inbound.handle_inbound(session, msg)
    except Exception:  # noqa: BLE001 — nunca 500 para a Evolution
        logger.exception("Falha ao processar resposta do WhatsApp")
        await session.rollback()
        return {"status": "error"}
    return {"status": action or "ignored"}
