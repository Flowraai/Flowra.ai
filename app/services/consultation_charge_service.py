"""Geração e cálculo dos lançamentos financeiros por consulta.

Ao marcar a consulta como realizada, cria-se um lançamento (idempotente). O
valor cheio e o repasse ao médico saem da situação do paciente:
- particular: repasse = valor cheio (consultório solo, sem rateio);
- convênio: repasse pela regra do plano (fixo ou percentual).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consultation_charge import ConsultationCharge
from app.models.health_plan import HealthPlan
from app.models.patient import Patient


def compute_doctor_cents(kind: str, gross_cents: int, plan: HealthPlan | None) -> int:
    """Repasse ao médico em centavos, dado o valor cheio e o convênio."""
    if kind == "convenio" and plan is not None:
        return plan.payout_for(gross_cents)
    return gross_cents  # particular (solo): médico recebe o valor cheio


async def generate_for_appointment(
    session: AsyncSession, appointment, patient: Patient
) -> ConsultationCharge | None:
    """Cria o lançamento da consulta, se ainda não existir. Idempotente."""
    existing = await session.scalar(
        select(ConsultationCharge).where(
            ConsultationCharge.appointment_id == appointment.id
        )
    )
    if existing is not None:
        return existing

    plan = patient.health_plan
    kind = "convenio" if plan is not None else "particular"
    # Sugestão de valor: convênio usa o valor de referência do plano; particular
    # começa em 0 e o médico ajusta ao marcar recebido.
    gross = (plan.default_consultation_cents or 0) if plan is not None else 0
    charge = ConsultationCharge(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=appointment.doctor_id,
        appointment_id=appointment.id,
        health_plan_id=plan.id if plan is not None else None,
        kind=kind,
        gross_cents=gross,
        doctor_cents=compute_doctor_cents(kind, gross, plan),
        status="pending",
    )
    session.add(charge)
    await session.flush()
    return charge
