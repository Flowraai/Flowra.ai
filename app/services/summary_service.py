"""Resumo da situação do paciente para o painel do médico.

Reúne o contexto (risco, check-ins recentes, adesão, alertas, próxima consulta) e
produz um resumo. Com LLM configurado, gera texto natural; sem chave, cai num
resumo determinístico (sempre disponível). A IA não diagnostica.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.alert import Alert
from app.models.checkin import CheckIn
from app.models.enums import AlertStatus, AppointmentStatus, RiskLevel
from app.models.patient import Patient
from app.protocol import psychiatry as P
from app.services.inactivity_service import days_since_checkin
from app.services.llm import chat_complete
from app.services.medication_service import adherence_summary

_RECENT = 5
_SYSTEM = (
    "Você é um assistente clínico. Resuma a situação do paciente em 2-3 frases, "
    "objetivo e direto, para um médico psiquiatra. Use SOMENTE os dados fornecidos, "
    "não invente nada. Você NÃO diagnostica — apenas resume o acompanhamento."
)


def _num(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


async def _gather(session: AsyncSession, patient: Patient) -> dict:
    now = datetime.now(timezone.utc)
    checkins = list(
        (
            await session.execute(
                select(CheckIn)
                .where(CheckIn.patient_id == patient.id)
                .order_by(CheckIn.created_at.desc())
                .limit(_RECENT)
            )
        )
        .scalars()
        .all()
    )
    moods = [m for m in (_num(c.structured_responses.get(P.Q_MOOD)) for c in checkins) if m is not None]
    anx = [a for a in (_num(c.structured_responses.get(P.Q_ANXIETY)) for c in checkins) if a is not None]
    crises = sum(
        1 for c in checkins if str(c.structured_responses.get(P.Q_CRISIS, "")).lower() == P.YES
    )
    open_alerts = await session.scalar(
        select(func.count()).select_from(Alert).where(
            Alert.patient_id == patient.id, Alert.status != AlertStatus.RESOLVED
        )
    )
    next_appt = await session.scalar(
        select(Appointment.scheduled_at)
        .where(
            Appointment.patient_id == patient.id,
            Appointment.status.in_((AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)),
            Appointment.scheduled_at >= now,
        )
        .order_by(Appointment.scheduled_at)
        .limit(1)
    )
    return {
        "current_risk": patient.current_risk.value,
        "days_since_checkin": days_since_checkin(patient, now),
        "recent_checkins": len(checkins),
        "avg_mood": _avg(moods),
        "avg_anxiety": _avg(anx),
        "crises_recent": crises,
        "adherence": await adherence_summary(session, patient.id, 30),
        "open_alerts": int(open_alerts or 0),
        "next_appointment": next_appt.isoformat() if next_appt else None,
    }


def _render_deterministic(patient: Patient, ctx: dict) -> str:
    risk = RiskLevel(ctx["current_risk"])
    parts = [f"{patient.name}: risco atual {risk.emoji} ({risk.value})."]
    if ctx["days_since_checkin"] is None:
        parts.append("Sem check-in registrado.")
    else:
        parts.append(f"Último check-in há {ctx['days_since_checkin']} dia(s).")
    if ctx["recent_checkins"]:
        mood = ctx["avg_mood"]
        anx = ctx["avg_anxiety"]
        bits = []
        if mood is not None:
            bits.append(f"humor médio {mood}/10")
        if anx is not None:
            bits.append(f"ansiedade média {anx}/10")
        if bits:
            parts.append(
                f"Nos últimos {ctx['recent_checkins']} check-ins: " + ", ".join(bits) + "."
            )
        if ctx["crises_recent"]:
            parts.append(f"{ctx['crises_recent']} episódio(s) de crise relatado(s).")
    adh = ctx["adherence"]
    responded = adh["taken"] + adh["later"] + adh["missed"]
    if responded:
        parts.append(
            f"Adesão à medicação: {adh['taken']}/{responded} tomadas "
            f"({round(adh['adherence_rate'] * 100)}%)."
        )
    if ctx["open_alerts"]:
        parts.append(f"{ctx['open_alerts']} alerta(s) em aberto.")
    return " ".join(parts)


async def patient_summary(session: AsyncSession, patient: Patient) -> dict:
    ctx = await _gather(session, patient)
    deterministic = _render_deterministic(patient, ctx)
    llm = await chat_complete(_SYSTEM, f"Contexto do paciente:\n{ctx}")
    if llm:
        return {"summary": llm, "generated_by": "llm", "context": ctx}
    return {"summary": deterministic, "generated_by": "deterministic", "context": ctx}
