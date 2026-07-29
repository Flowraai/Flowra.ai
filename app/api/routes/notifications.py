"""Rotas de notificação do médico (validação de canais)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.notification import NotificationTestResult
from app.services.notification_channels import get_active_channels
from app.services.notifications import target_for_channel

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test", response_model=NotificationTestResult)
async def test_notification(
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> NotificationTestResult:
    """Envia uma notificação de teste para validar a configuração dos canais."""
    email = doctor.notification_email
    if not email:
        user = await session.get(User, doctor.user_id)
        email = user.email if user else f"doctor:{doctor.id}"
    phone = doctor.notification_phone

    results: dict[str, str] = {}
    for channel in get_active_channels():
        target = target_for_channel(channel.channel_type, email, phone)
        if not target:
            results[channel.channel_type.value] = "failed: sem contato para este canal"
            continue
        try:
            await channel.send(
                target=target,
                subject="[Flowra Care] Teste de notificação",
                body="Esta é uma notificação de teste do Flowra Care. Se você recebeu, o canal está funcionando.",
            )
            results[channel.channel_type.value] = "sent"
        except Exception as exc:  # noqa: BLE001 — reporta a falha por canal
            results[channel.channel_type.value] = f"failed: {exc}"

    return NotificationTestResult(target=email, results=results)
