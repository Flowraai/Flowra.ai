"""Serviço de notificações — alerta o médico e registra cada entrega.

Roteia o alerta para os canais configurados, persiste um `Notification` por
tentativa (auditável) e nunca deixa a falha de um canal derrubar o check-in.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.doctor import Doctor
from app.models.enums import AlertUrgency, AuditAction, NotificationChannel, NotificationStatus
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.user import User
from app.services import audit
from app.services.notification_channels import get_active_channels
from app.services.push_service import push_to_doctor

logger = logging.getLogger("flowra_care.notifications")


async def doctor_notification_contacts(
    session: AsyncSession, patient: Patient
) -> tuple[str, str | None]:
    """Contatos do médico responsável: (e-mail, telefone). E-mail sempre tem fallback."""
    email = f"doctor:{patient.doctor_id}"
    phone: str | None = None
    doctor = await session.get(Doctor, patient.doctor_id)
    if doctor is not None:
        phone = doctor.notification_phone
        if doctor.notification_email:
            email = doctor.notification_email
        else:
            user = await session.get(User, doctor.user_id)
            if user is not None and user.email:
                email = user.email
    return email, phone


def target_for_channel(
    channel_type: NotificationChannel, email: str, phone: str | None
) -> str | None:
    """WhatsApp usa telefone; os demais canais usam o e-mail."""
    if channel_type is NotificationChannel.WHATSAPP:
        return phone
    return email


async def send_plain(target: str, subject: str, body: str) -> None:
    """Envia uma mensagem avulsa (ex.: e-mail de reset de senha) pelos canais ativos.

    Não persiste registro (não é um alerta); falha de canal apenas é logada.
    """
    for channel in get_active_channels():
        try:
            await channel.send(target=target, subject=subject, body=body)
        except Exception as exc:  # noqa: BLE001
            logger.error("Falha ao enviar mensagem via %s: %s", channel.channel_type.value, exc)


def _render(alert: Alert) -> tuple[str, str]:
    """Conteúdo enviado a canais externos (WhatsApp/e-mail/webhook) e push.

    LGPD — minimização: dado de saúde é sensível e estes canais são de terceiros
    (Meta, provedor de e-mail, APNs/FCM) e aparecem em tela de bloqueio. NÃO
    incluímos nome do paciente, nível de risco nem motivo clínico; só sinalizamos
    que há um alerta e sua urgência. O detalhe clínico fica no painel, sob login.
    """
    if alert.urgency is AlertUrgency.IMMEDIATE:
        subject = "[Flowra Care] 🔴 Alerta urgente"
        detail = "um alerta URGENTE"
    else:
        subject = "[Flowra Care] 🟠 Novo alerta de acompanhamento"
        detail = "um alerta de acompanhamento"
    body = (
        f"Um paciente sob seu acompanhamento gerou {detail}. "
        "Abra o painel do Flowra Care para revisar o caso.\n"
        "Por privacidade (LGPD), os detalhes clínicos ficam apenas no painel."
    )
    return subject, body


async def dispatch_alert(
    session: AsyncSession, *, alert: Alert, patient: Patient, email: str, phone: str | None = None
) -> list[Notification]:
    subject, body = _render(alert)
    records: list[Notification] = []

    for channel in get_active_channels():
        target = target_for_channel(channel.channel_type, email, phone)
        notification = Notification(
            alert_id=alert.id,
            channel=channel.channel_type,
            target=target or "",
            status=NotificationStatus.QUEUED,
        )
        session.add(notification)
        if not target:
            notification.status = NotificationStatus.FAILED
            notification.error = "sem contato do médico para este canal"
        else:
            try:
                await channel.send(target=target, subject=subject, body=body)
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.now(timezone.utc)
            except Exception as exc:  # noqa: BLE001 — falha de canal não quebra o fluxo
                notification.status = NotificationStatus.FAILED
                notification.error = str(exc)[:500]
                logger.error(
                    "Falha ao notificar via %s (paciente=%s): %s",
                    channel.channel_type.value, patient.id, exc,
                )
        records.append(notification)

    # Push ao médico (além dos canais), para quem tiver device registrado.
    await push_to_doctor(session, patient.doctor_id, subject, body)

    await session.flush()
    await audit.record(
        session,
        action=AuditAction.ALERT_NOTIFICATION_SENT,
        actor="system",
        entity_type="alert",
        entity_id=alert.id,
        metadata={"results": {n.channel.value: n.status.value for n in records}},
    )
    return records
