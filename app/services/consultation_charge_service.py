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
from app.models.doctor import Doctor
from app.models.health_plan import HealthPlan
from app.models.patient import Patient


def compute_doctor_cents(kind: str, gross_cents: int, plan: HealthPlan | None) -> int:
    """Base do repasse em centavos (antes do rateio): valor cheio no particular,
    regra do plano no convênio."""
    if kind == "convenio" and plan is not None:
        return plan.payout_for(gross_cents)
    return gross_cents  # particular: valor cheio da consulta


def compute_split(base_cents: int, clinic_share_percent: int) -> tuple[int, int]:
    """Divide a base entre médico (líquido) e clínica, dado o % da clínica.

    Retorna (doctor_cents, clinic_cents). Solo (0%) -> (base, 0)."""
    share = max(0, min(100, clinic_share_percent or 0))
    clinic = base_cents * share // 100
    return base_cents - clinic, clinic


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
    base = compute_doctor_cents(kind, gross, plan)
    doctor = await session.get(Doctor, appointment.doctor_id)
    doctor_cents, clinic_cents = compute_split(
        base, doctor.clinic_share_percent if doctor else 0
    )
    charge = ConsultationCharge(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=appointment.doctor_id,
        appointment_id=appointment.id,
        health_plan_id=plan.id if plan is not None else None,
        kind=kind,
        gross_cents=gross,
        doctor_cents=doctor_cents,
        clinic_cents=clinic_cents,
        status="pending",
    )
    session.add(charge)
    await session.flush()
    return charge
