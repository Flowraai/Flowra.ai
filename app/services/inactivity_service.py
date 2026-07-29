"""Detecção de não-adesão: pacientes que pararam de responder aos check-ins.

Gera um alerta (🟠, rotina) para pacientes ativos sem check-in há N dias
(`INACTIVITY_ALERT_DAYS`). Idempotente: só cria se não houver alerta de
inatividade em aberto (alertas de inatividade não têm `checkin_id`).

Pode ser disparado por um endpoint do médico ou por um job agendado
(app/scripts/scan_inactivity.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.alert import Alert
from app.models.enums import AlertStatus, AlertUrgency, AuditAction, RiskLevel
from app.models.patient import Patient
from app.services import audit
from app.services.notifications import dispatch_alert, doctor_notification_target


def days_since_checkin(patient: Patient, now: datetime | None = None) -> int | None:
    now = now or datetime.now(timezone.utc)
    reference = patient.last_checkin_at or patient.created_at
    if reference is None:
        return None
    return (now - reference).days


def is_inactive(patient: Patient, now: datetime | None = None) -> bool:
    days = days_since_checkin(patient, now)
    return days is not None and days >= settings.inactivity_alert_days


async def scan_inactivity(
    session: AsyncSession, doctor_id: uuid.UUID | None = None
) -> list[Alert]:
    """Cria alertas de inatividade. Se `doctor_id` for dado, restringe a ele."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=settings.inactivity_alert_days)

    # Alerta de inatividade em aberto já existente para o paciente (dedup).
    open_inactivity = (
        select(Alert.id)
        .where(
            Alert.patient_id == Patient.id,
            Alert.checkin_id.is_(None),
            Alert.status != AlertStatus.RESOLVED,
        )
        .correlate(Patient)
    )

    query = select(Patient).where(
        Patient.is_active.is_(True),
        or_(
            and_(Patient.last_checkin_at.is_(None), Patient.created_at <= threshold),
            Patient.last_checkin_at <= threshold,
        ),
        ~exists(open_inactivity),
    )
    if doctor_id is not None:
        query = query.where(Patient.doctor_id == doctor_id)

    patients = list((await session.execute(query)).scalars().all())

    created: list[Alert] = []
    for patient in patients:
        days = days_since_checkin(patient, now)
        reason = (
            f"Paciente sem check-in há {days} dias"
            if days is not None
            else "Paciente sem check-in registrado"
        )
        alert = Alert(
            patient_id=patient.id,
            checkin_id=None,
            level=RiskLevel.ORANGE,
            urgency=AlertUrgency.ROUTINE,
            reason=reason,
            reasons_detail=[reason],
        )
        session.add(alert)
        await session.flush()

        await audit.record(
            session,
            action=AuditAction.ALERT_CREATED,
            actor="system",
            entity_type="alert",
            entity_id=alert.id,
            metadata={"kind": "inactivity", "days": days},
        )
        target = await doctor_notification_target(session, patient)
        await dispatch_alert(session, alert=alert, patient=patient, target=target)
        created.append(alert)

    return created
