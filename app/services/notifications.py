"""Serviço de notificações — alerta o médico quando o risco exige atenção.

MVP: registra a notificação (log) e deixa o alerta persistido para o painel.
Integrações reais (e-mail/push/WhatsApp) implementam a mesma interface.
"""

from __future__ import annotations

import logging

from app.models.alert import Alert
from app.models.enums import AlertUrgency
from app.models.patient import Patient

logger = logging.getLogger("flowra_care.notifications")


class NotificationService:
    async def notify_doctor(self, alert: Alert, patient: Patient) -> None:
        urgency_label = (
            "IMEDIATO" if alert.urgency is AlertUrgency.IMMEDIATE else "não urgente"
        )
        logger.warning(
            "Alerta %s (%s) — paciente=%s risco=%s motivo=%s",
            urgency_label,
            alert.urgency.value,
            patient.id,
            alert.level.value,
            alert.reason,
        )
        # TODO (fase 1/2): enviar e-mail/push conforme urgência; registrar entrega.


notification_service = NotificationService()
