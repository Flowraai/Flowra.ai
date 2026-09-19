"""Lançamentos financeiros por consulta: listar, gerar e receber/cancelar.

Camada de controle gerencial (a receber / recebido). Sem cobrança online no MVP.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember, require_finance_member, scope_query
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.consultation_charge import ConsultationCharge
from app.models.doctor import Doctor
from app.models.enums import ClinicRole
from app.models.health_plan import HealthPlan
from app.models.patient import Patient
from app.schemas.consultation_charge import (
    ChargeBucket,
    ChargeMonth,
    ChargePlanBucket,
    ChargeRead,
    ChargeSummary,
    ChargeUpdate,
    PixCode,
)
from app.services.consultation_charge_service import compute_doctor_cents, generate_for_appointment
from app.services.pix import build_pix_payload

router = APIRouter(tags=["charges"])


def _scope_ok(row, member: CurrentMember) -> bool:
    """A linha (paciente/consulta/cobrança) está no escopo do membro?

    Médico vê o que é dele (doctor_id); gestão/recepção veem o tenant inteiro.
    """
    if member.role is ClinicRole.DOCTOR and member.doctor is not None:
        return row.doctor_id == member.doctor.id
    return row.tenant_id == member.tenant_id


async def _owned_patient(
    session: AsyncSession, member: CurrentMember, patient_id: uuid.UUID
) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or not _scope_ok(patient, member):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


async def _owned_charge(
    session: AsyncSession, member: CurrentMember, charge_id: uuid.UUID
) -> ConsultationCharge:
    charge = await session.get(ConsultationCharge, charge_id)
    if charge is None or not _scope_ok(charge, member):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lançamento não encontrado.")
    return charge


def _read(charge: ConsultationCharge, plan_name: str | None = None) -> ChargeRead:
    out = ChargeRead.model_validate(charge)
    out.health_plan_name = plan_name
    return out


@router.get("/patients/{patient_id}/charges", response_model=list[ChargeRead])
async def list_patient_charges(
    patient_id: uuid.UUID,
    member: CurrentMember = Depends(require_finance_member),
    session: AsyncSession = Depends(get_db),
) -> list[ChargeRead]:
    await _owned_patient(session, member, patient_id)
    rows = list(
        (
            await session.execute(
                select(ConsultationCharge)
                .where(ConsultationCharge.patient_id == patient_id)
                .order_by(ConsultationCharge.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    names = await _plan_names(session, rows)
    return [_read(c, names.get(c.health_plan_id)) for c in rows]


@router.get("/charges", response_model=list[ChargeRead])
async def list_doctor_charges(
    status_filter: str | None = Query(default=None, alias="status"),
    start: datetime | None = None,
    end: datetime | None = None,
    member: CurrentMember = Depends(require_finance_member),
    session: AsyncSession = Depends(get_db),
) -> list[ChargeRead]:
    """Lançamentos do painel financeiro, com filtro por status e período. O escopo
    segue o papel: médico vê os seus; gestão/recepção veem os da clínica."""
    stmt = scope_query(select(ConsultationCharge), ConsultationCharge, member)
    if status_filter:
        stmt = stmt.where(ConsultationCharge.status == status_filter)
    if start is not None:
        stmt = stmt.where(ConsultationCharge.created_at >= start)
    if end is not None:
        stmt = stmt.where(ConsultationCharge.created_at <= end)
    stmt = stmt.order_by(ConsultationCharge.created_at.desc())
    rows = list((await session.execute(stmt)).scalars().all())
    plan_names = await _plan_names(session, rows)
    pt_names = await _patient_names(session, rows)
    out = []
    for c in rows:
        r = _read(c, plan_names.get(c.health_plan_id))
        r.patient_name = pt_names.get(c.patient_id)
        out.append(r)
    return out


@router.get("/charges/summary", response_model=ChargeSummary)
async def charges_summary(
    start: datetime | None = None,
    end: datetime | None = None,
    member: CurrentMember = Depends(require_finance_member),
    session: AsyncSession = Depends(get_db),
) -> ChargeSummary:
    """Agrega o financeiro do período: a receber × recebido, por tipo/convênio e
    a série mensal para o gráfico. Recorte por competência (created_at)."""
    stmt = scope_query(select(ConsultationCharge), ConsultationCharge, member)
    if start is not None:
        stmt = stmt.where(ConsultationCharge.created_at >= start)
    if end is not None:
        stmt = stmt.where(ConsultationCharge.created_at <= end)
    rows = list((await session.execute(stmt)).scalars().all())
    plan_names = await _plan_names(session, rows)

    particular = ChargeBucket()
    convenio = ChargeBucket()
    cancelled = 0
    denied_count = 0
    denied_cents = 0
    by_plan: dict[uuid.UUID | None, ChargePlanBucket] = {}
    months: dict[str, ChargeMonth] = {}

    for c in rows:
        if c.status == "cancelled":
            cancelled += 1
            continue
        if c.status == "denied":
            denied_count += 1
            denied_cents += c.doctor_cents
            continue
        bucket = convenio if c.kind == "convenio" else particular
        pkey = c.health_plan_id
        if pkey not in by_plan:
            name = plan_names.get(pkey) if pkey else "Particular"
            by_plan[pkey] = ChargePlanBucket(health_plan_id=pkey, name=name or "Convênio")
        pbucket = by_plan[pkey]
        month = c.created_at.strftime("%Y-%m")
        if month not in months:
            months[month] = ChargeMonth(month=month)
        m = months[month]

        for b in (bucket, pbucket):
            b.count += 1
        if c.status == "received":
            bucket.received_cents += c.doctor_cents
            pbucket.received_cents += c.doctor_cents
            m.received_cents += c.doctor_cents
        else:  # pending ou billed (faturado, ainda a receber)
            bucket.to_receive_cents += c.doctor_cents
            pbucket.to_receive_cents += c.doctor_cents
            m.pending_cents += c.doctor_cents

    return ChargeSummary(
        to_receive_cents=particular.to_receive_cents + convenio.to_receive_cents,
        received_cents=particular.received_cents + convenio.received_cents,
        denied_cents=denied_cents,
        cancelled_count=cancelled,
        denied_count=denied_count,
        particular=particular,
        convenio=convenio,
        by_plan=sorted(by_plan.values(), key=lambda b: b.received_cents + b.to_receive_cents, reverse=True),
        monthly=[months[k] for k in sorted(months)],
    )


_STATUS_LABEL = {
    "pending": "A receber", "billed": "Faturado", "received": "Recebido",
    "denied": "Glosado", "cancelled": "Cancelado",
}


def _brl(cents: int) -> str:
    return f"{cents / 100:.2f}".replace(".", ",")


@router.get("/charges/export.csv")
async def export_charges_csv(
    start: datetime | None = None,
    end: datetime | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    member: CurrentMember = Depends(require_finance_member),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Exporta o movimento financeiro em CSV (para o contador). Recorte por
    período e status, como no painel. Separador ';' e decimais com vírgula
    (padrão do Excel em pt-BR)."""
    stmt = scope_query(select(ConsultationCharge), ConsultationCharge, member)
    if status_filter:
        stmt = stmt.where(ConsultationCharge.status == status_filter)
    if start is not None:
        stmt = stmt.where(ConsultationCharge.created_at >= start)
    if end is not None:
        stmt = stmt.where(ConsultationCharge.created_at <= end)
    stmt = stmt.order_by(ConsultationCharge.created_at)
    rows = list((await session.execute(stmt)).scalars().all())
    plan_names = await _plan_names(session, rows)
    pt_names = await _patient_names(session, rows)

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([
        "Data", "Paciente", "Tipo", "Convênio", "Valor bruto (R$)",
        "Repasse (R$)", "Situação", "Forma", "Recebido em", "Observações",
    ])
    for c in rows:
        w.writerow([
            c.created_at.strftime("%d/%m/%Y"),
            pt_names.get(c.patient_id, ""),
            "Convênio" if c.kind == "convenio" else "Particular",
            plan_names.get(c.health_plan_id, "") if c.health_plan_id else "",
            _brl(c.gross_cents),
            _brl(c.doctor_cents),
            _STATUS_LABEL.get(c.status, c.status),
            c.payment_method or "",
            c.received_at.strftime("%d/%m/%Y") if c.received_at else "",
            c.notes or "",
        ])
    # BOM para o Excel reconhecer o UTF-8 (acentos).
    data = "﻿" + buf.getvalue()
    filename = f"financeiro-flowra-{datetime.now(timezone.utc):%Y%m%d}.csv"
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/appointments/{appointment_id}/charge",
    response_model=ChargeRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_charge(
    appointment_id: uuid.UUID,
    member: CurrentMember = Depends(require_finance_member),
    session: AsyncSession = Depends(get_db),
) -> ChargeRead:
    """Gera o lançamento de uma consulta manualmente (idempotente).

    Útil para consultas realizadas antes de o financeiro existir.
    """
    appt = await session.get(Appointment, appointment_id)
    if appt is None or not _scope_ok(appt, member):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
    patient = await session.get(Patient, appt.patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    charge = await generate_for_appointment(session, appt, patient)
    plan_name = patient.health_plan.name if patient.health_plan else None
    return _read(charge, plan_name)


@router.patch("/charges/{charge_id}", response_model=ChargeRead)
async def update_charge(
    charge_id: uuid.UUID,
    payload: ChargeUpdate,
    member: CurrentMember = Depends(require_finance_member),
    session: AsyncSession = Depends(get_db),
) -> ChargeRead:
    charge = await _owned_charge(session, member, charge_id)
    data = payload.model_dump(exclude_unset=True)

    if "gross_cents" in data:
        charge.gross_cents = data["gross_cents"]
        # Recalcula o repasse pela regra do convênio (ou = valor cheio no particular),
        # a menos que o médico informe doctor_cents explicitamente.
        if "doctor_cents" not in data:
            plan = (
                await session.get(HealthPlan, charge.health_plan_id)
                if charge.health_plan_id
                else None
            )
            charge.doctor_cents = compute_doctor_cents(charge.kind, charge.gross_cents, plan)
    if "doctor_cents" in data:
        charge.doctor_cents = data["doctor_cents"]
    if "notes" in data:
        charge.notes = data["notes"]
    if "payment_method" in data:
        charge.payment_method = data["payment_method"]
    if "status" in data:
        charge.status = data["status"]
        if data["status"] == "received":
            charge.received_at = charge.received_at or datetime.now(timezone.utc)
        else:
            charge.received_at = None

    plan_name = None
    if charge.health_plan_id:
        plan = await session.get(HealthPlan, charge.health_plan_id)
        plan_name = plan.name if plan else None
    return _read(charge, plan_name)


@router.get("/charges/{charge_id}/pix", response_model=PixCode)
async def charge_pix(
    charge_id: uuid.UUID,
    member: CurrentMember = Depends(require_finance_member),
    session: AsyncSession = Depends(get_db),
) -> PixCode:
    """Gera o PIX copia-e-cola de uma cobrança particular.

    Só faz sentido para cobrança do paciente (particular): convênio é pago pelo
    plano. Usa a chave PIX do médico DONO da cobrança (a recepção pode gerar o
    código de qualquer médico da clínica).
    """
    charge = await _owned_charge(session, member, charge_id)
    if charge.kind != "particular":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PIX é só para cobrança particular (convênio é pago pelo plano).",
        )
    if charge.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Lançamento cancelado."
        )
    doctor = await session.get(Doctor, charge.doctor_id)
    if doctor is None or not doctor.pix_key or not doctor.pix_city:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure a chave PIX e a cidade do médico em Ajustes para gerar a cobrança.",
        )
    # txid a partir do id da cobrança (rastreável na conciliação manual).
    txid = charge.id.hex[:25]
    payload = build_pix_payload(
        key=doctor.pix_key,
        receiver_name=doctor.name,
        city=doctor.pix_city,
        amount_cents=charge.gross_cents,
        txid=txid,
    )
    return PixCode(
        payload=payload,
        amount_cents=charge.gross_cents,
        receiver=doctor.name,
        city=doctor.pix_city,
    )


async def _plan_names(
    session: AsyncSession, charges: list[ConsultationCharge]
) -> dict[uuid.UUID, str]:
    ids = {c.health_plan_id for c in charges if c.health_plan_id}
    if not ids:
        return {}
    rows = (
        await session.execute(select(HealthPlan.id, HealthPlan.name).where(HealthPlan.id.in_(ids)))
    ).all()
    return {pid: name for pid, name in rows}


async def _patient_names(
    session: AsyncSession, charges: list[ConsultationCharge]
) -> dict[uuid.UUID, str]:
    ids = {c.patient_id for c in charges}
    if not ids:
        return {}
    # patient.name é EncryptedText — carregar via ORM decifra em memória.
    rows = list(
        (await session.execute(select(Patient).where(Patient.id.in_(ids)))).scalars().all()
    )
    return {p.id: p.name for p in rows}
