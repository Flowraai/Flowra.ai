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
from app.models.enums import AlertUrgency, AuditAction, NotificationStatus
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.user import User
from app.services import audit
from app.services.notification_channels import get_active_channels

logger = logging.getLogger("flowra_care.notifications")


async def doctor_notification_target(session: AsyncSession, patient: Patient) -> str:
    """E-mail do médico responsável (destino da notificação); fallback estável."""
    doctor = await session.get(Doctor, patient.doctor_id)
    if doctor is not None:
        user = await session.get(User, doctor.user_id)
        if user is not None and user.email:
            return user.email
    return f"doctor:{patient.doctor_id}"


async def send_plain(target: str, subject: str, body: str) -> None:
    """Envia uma mensagem avulsa (ex.: e-mail de reset de senha) pelos canais ativos.

    Não persiste registro (não é um alerta); falha de canal apenas é logada.
    """
    for channel in get_active_channels():
        try:
            await channel.send(target=target, subject=subject, body=body)
        except Exception as exc:  # noqa: BLE001
            logger.error("Falha ao enviar mensagem via %s: %s", channel.channel_type.value, exc)


def _render(alert: Alert, patient: Patient) -> tuple[str, str]:
    prefix = "🔴 URGENTE" if alert.urgency is AlertUrgency.IMMEDIATE else "🟠 Acompanhamento"
    subject = f"[Flowra Care] {prefix} — paciente {patient.name}"
    body = (
        f"Paciente: {patient.name}\n"
        f"Nível de risco: {alert.level.value}\n"
        f"Urgência: {alert.urgency.value}\n"
        f"Motivo(s): {alert.reason}\n\n"
        "Acesse o painel para revisar o caso.\n"
        "Lembrete: a priorização é apoio à decisão e não substitui o julgamento clínico."
    )
    return subject, body


async def dispatch_alert(
    session: AsyncSession, *, alert: Alert, patient: Patient, target: str
) -> list[Notification]:
    subject, body = _render(alert, patient)
    records: list[Notification] = []

    for channel in get_active_channels():
        notification = Notification(
            alert_id=alert.id,
            channel=channel.channel_type,
            target=target,
            status=NotificationStatus.QUEUED,
        )
        session.add(notification)
        try:
            await channel.send(target=target, subject=subject, body=body)
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now(timezone.utc)
        except Exception as exc:  # noqa: BLE001 — falha de canal não pode quebrar o fluxo
            notification.status = NotificationStatus.FAILED
            notification.error = str(exc)[:500]
            logger.error(
                "Falha ao notificar via %s (paciente=%s): %s",
                channel.channel_type.value, patient.id, exc,
            )
        records.append(notification)

    await session.flush()
    await audit.record(
        session,
        action=AuditAction.ALERT_NOTIFICATION_SENT,
        actor="system",
        entity_type="alert",
        entity_id=alert.id,
        metadata={
            "target": target,
            "results": {n.channel.value: n.status.value for n in records},
        },
    )
    return records
