"""WhatsApp por médico (Evolution API): conectar o próprio número por QR.

Cada médico pareia o próprio número; as mensagens aos pacientes dele saem desse
número. Requer a Evolution API configurada no servidor (EVOLUTION_API_URL/KEY).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.doctor import Doctor
from app.schemas.whatsapp import WhatsAppConnect, WhatsAppStatus
from app.services import evolution

logger = logging.getLogger("flowra_care.whatsapp")

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


def _require_configured() -> None:
    if not evolution.configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp não está configurado no servidor (Evolution API).",
        )


def _bad_gateway(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Não foi possível {action} agora. Tente novamente.",
    )


@router.get("/status", response_model=WhatsAppStatus)
async def whatsapp_status(
    doctor: Doctor = Depends(get_current_doctor),
) -> WhatsAppStatus:
    _require_configured()
    if not doctor.whatsapp_instance:
        return WhatsAppStatus(connected=False, state="disconnected")
    try:
        st = await evolution.state(doctor.whatsapp_instance)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao consultar estado do WhatsApp")
        raise _bad_gateway("consultar o WhatsApp")
    return WhatsAppStatus(connected=st == "open", state=st)


@router.post("/connect", response_model=WhatsAppConnect)
async def whatsapp_connect(
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> WhatsAppConnect:
    """Cria a instância do médico (se preciso) e devolve o QR para parear."""
    _require_configured()
    name = doctor.whatsapp_instance or evolution.instance_name_for(doctor.id)
    try:
        await evolution.ensure_instance(name)
        result = await evolution.connect(name)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao conectar o WhatsApp")
        raise _bad_gateway("conectar o WhatsApp")
    doctor.whatsapp_instance = name  # persiste o vínculo
    await session.flush()
    return WhatsAppConnect(
        state=result.get("state"), qr=result.get("qr"), pairing_code=result.get("pairing_code")
    )


@router.post("/disconnect", response_model=WhatsAppStatus)
async def whatsapp_disconnect(
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> WhatsAppStatus:
    _require_configured()
    if doctor.whatsapp_instance:
        try:
            await evolution.disconnect(doctor.whatsapp_instance)
        except Exception:  # noqa: BLE001 — desconectar é best-effort
            logger.warning("Falha ao desconectar o WhatsApp (seguindo)")
        doctor.whatsapp_instance = None
        await session.flush()
    return WhatsAppStatus(connected=False, state="disconnected")
