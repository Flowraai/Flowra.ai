"""Serviço de push: resolve os device tokens do destinatário e envia via provedor."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device_token import DeviceToken
from app.models.enums import DeviceOwnerType
from app.services.push_provider import get_push_provider


async def register_device(
    session: AsyncSession,
    *,
    owner_type: DeviceOwnerType,
    owner_id: uuid.UUID,
    token: str,
    platform: str,
) -> DeviceToken:
    """Registra (ou reassocia) um device token ao dono. Idempotente por token."""
    existing = await session.scalar(select(DeviceToken).where(DeviceToken.token == token))
    if existing is not None:
        existing.owner_type = owner_type
        existing.owner_id = owner_id
        existing.platform = platform
        existing.is_active = True
        return existing
    device = DeviceToken(
        owner_type=owner_type, owner_id=owner_id, token=token, platform=platform
    )
    session.add(device)
    await session.flush()
    return device


async def unregister_device(session: AsyncSession, token: str) -> bool:
    device = await session.scalar(select(DeviceToken).where(DeviceToken.token == token))
    if device is None:
        return False
    device.is_active = False
    return True


async def send_push(
    session: AsyncSession,
    *,
    owner_type: DeviceOwnerType,
    owner_id: uuid.UUID,
    title: str,
    body: str,
) -> dict:
    """Envia um push para todos os dispositivos ativos do dono."""
    tokens = list(
        (
            await session.execute(
                select(DeviceToken.token).where(
                    DeviceToken.owner_type == owner_type,
                    DeviceToken.owner_id == owner_id,
                    DeviceToken.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    if not tokens:
        return {"sent": 0, "results": {}}
    results = await get_push_provider().send(tokens, title, body)
    sent = sum(1 for v in results.values() if v == "sent")
    return {"sent": sent, "results": results}


async def push_to_patient(
    session: AsyncSession, patient_id: uuid.UUID, title: str, body: str
) -> None:
    """Envia push aos dispositivos do paciente (no-op se não houver device)."""
    await send_push(
        session, owner_type=DeviceOwnerType.PATIENT, owner_id=patient_id, title=title, body=body
    )


async def push_to_doctor(
    session: AsyncSession, doctor_id: uuid.UUID, title: str, body: str
) -> None:
    """Envia push aos dispositivos do médico (no-op se não houver device)."""
    await send_push(
        session, owner_type=DeviceOwnerType.DOCTOR, owner_id=doctor_id, title=title, body=body
    )
