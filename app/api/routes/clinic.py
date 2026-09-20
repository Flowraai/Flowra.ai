"""Equipe da clínica: convites e gestão de integrantes (só o dono)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember, require_clinical_member, require_owner
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.consultation_charge import ConsultationCharge
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, ClinicRole, RiskLevel
from app.models.invitation import Invitation
from app.models.membership import Membership
from app.models.patient import Patient
from app.schemas.auth import TokenPair
from app.schemas.clinic import (
    ClinicDashboard,
    DoctorStat,
    InvitationAccept,
    InvitationCreate,
    InvitationRead,
    MemberRead,
    MemberUpdate,
    RiskCounts,
)
from app.models.user import User
from app.schemas.patient import CareTeamMemberRead
from app.services import clinic_service
from app.services.attention_service import compute_attention

router = APIRouter(prefix="/clinic", tags=["clinic"])


def _invite_out(inv: Invitation) -> InvitationRead:
    return InvitationRead(
        id=inv.id, email=inv.email, role=inv.role.value,
        can_view_finance=inv.can_view_finance, expires_at=inv.expires_at,
        accepted_at=inv.accepted_at, created_at=inv.created_at,
    )


@router.post("/invitations", response_model=InvitationRead, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    payload: InvitationCreate,
    member: CurrentMember = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> InvitationRead:
    invite, _raw = await clinic_service.create_invitation(session, member, payload)
    return _invite_out(invite)


@router.get("/invitations", response_model=list[InvitationRead])
async def list_invitations(
    member: CurrentMember = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> list[InvitationRead]:
    """Convites pendentes (ainda não aceitos) da clínica."""
    rows = list(
        (
            await session.execute(
                select(Invitation)
                .where(
                    Invitation.tenant_id == member.tenant_id,
                    Invitation.accepted_at.is_(None),
                )
                .order_by(Invitation.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_invite_out(i) for i in rows]


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    member: CurrentMember = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> None:
    invite = await session.get(Invitation, invitation_id)
    if invite is None or invite.tenant_id != member.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convite não encontrado.")
    await session.delete(invite)


@router.post("/invitations/accept", response_model=TokenPair)
async def accept_invitation(
    payload: InvitationAccept,
    session: AsyncSession = Depends(get_db),
) -> TokenPair:
    """Aceita o convite (público): cria o acesso e já loga o convidado."""
    user = await clinic_service.accept_invitation(session, payload)
    access, refresh = await clinic_service.issue_tokens(session, user)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.get("/doctors", response_model=list[CareTeamMemberRead])
async def list_clinic_doctors(
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> list[CareTeamMemberRead]:
    """Médicos da clínica (para montar a equipe de cuidado de um paciente)."""
    rows = list(
        (await session.execute(select(Doctor).where(Doctor.tenant_id == member.tenant_id)))
        .scalars()
        .all()
    )
    return [
        CareTeamMemberRead(doctor_id=d.id, name=d.name, specialty=d.specialty, is_primary=False)
        for d in rows
    ]


@router.get("/members", response_model=list[MemberRead])
async def list_members(
    member: CurrentMember = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> list[MemberRead]:
    rows = list(
        (
            await session.execute(
                select(Membership, User.email)
                .join(User, User.id == Membership.user_id)
                .where(Membership.tenant_id == member.tenant_id)
                .order_by(Membership.created_at)
            )
        ).all()
    )
    # Nomes dos médicos do tenant (para exibir junto).
    names = {
        d.user_id: d.name
        for d in (
            await session.execute(select(Doctor).where(Doctor.tenant_id == member.tenant_id))
        )
        .scalars()
        .all()
    }
    out = []
    for m, email in rows:
        out.append(MemberRead(
            id=m.id, user_id=m.user_id, email=email, name=names.get(m.user_id),
            role=m.role.value, is_active=m.is_active, can_view_finance=m.can_view_finance,
            is_self=(m.user_id == member.user.id),
        ))
    return out


@router.patch("/members/{membership_id}", response_model=MemberRead)
async def update_member(
    membership_id: uuid.UUID,
    payload: MemberUpdate,
    member: CurrentMember = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> MemberRead:
    target = await session.get(Membership, membership_id)
    if target is None or target.tenant_id != member.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integrante não encontrado.")
    if target.role is ClinicRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível alterar o dono aqui."
        )

    data = payload.model_dump(exclude_unset=True)
    if "is_active" in data:
        target.is_active = data["is_active"]
    if "can_view_finance" in data:
        target.can_view_finance = data["can_view_finance"]
    if "role" in data and data["role"] is not None:
        new_role = ClinicRole(data["role"])
        target.role = new_role
        # Virar médico exige um perfil clínico (Doctor) no tenant.
        if new_role is ClinicRole.DOCTOR:
            has_doctor = (
                await session.execute(
                    select(Doctor).where(
                        Doctor.user_id == target.user_id, Doctor.tenant_id == target.tenant_id
                    )
                )
            ).scalar_one_or_none()
            if has_doctor is None:
                user = await session.get(User, target.user_id)
                session.add(Doctor(
                    user_id=target.user_id, tenant_id=target.tenant_id,
                    name=(user.email.split("@")[0] if user else "Profissional"),
                ))

    email = (await session.get(User, target.user_id)).email
    doctor = (
        await session.execute(
            select(Doctor).where(
                Doctor.user_id == target.user_id, Doctor.tenant_id == target.tenant_id
            )
        )
    ).scalar_one_or_none()
    return MemberRead(
        id=target.id, user_id=target.user_id, email=email,
        name=doctor.name if doctor else None, role=target.role.value,
        is_active=target.is_active, can_view_finance=target.can_view_finance,
        is_self=(target.user_id == member.user.id),
    )


_OPEN = (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)


@router.get("/dashboard", response_model=ClinicDashboard)
async def clinic_dashboard(
    start: datetime | None = None,
    end: datetime | None = None,
    member: CurrentMember = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> ClinicDashboard:
    """Visão gerencial da clínica (só o dono): pacientes, risco, agenda, financeiro
    e o comparativo por médico. Período padrão: mês corrente."""
    now = datetime.now(timezone.utc)
    period_start = start or now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = end or now
    tid = member.tenant_id

    # --- Pacientes: total, por risco e por médico ---
    risk_rows = (
        await session.execute(
            select(Patient.current_risk, func.count())
            .where(Patient.tenant_id == tid, Patient.is_active.is_(True))
            .group_by(Patient.current_risk)
        )
    ).all()
    risk = RiskCounts()
    patients_total = 0
    for level, count in risk_rows:
        patients_total += count
        if level == RiskLevel.GREEN:
            risk.green = count
        elif level == RiskLevel.YELLOW:
            risk.yellow = count
        elif level == RiskLevel.ORANGE:
            risk.orange = count
        elif level == RiskLevel.RED:
            risk.red = count

    pt_by_doctor = dict(
        (
            await session.execute(
                select(Patient.doctor_id, func.count())
                .where(Patient.tenant_id == tid, Patient.is_active.is_(True))
                .group_by(Patient.doctor_id)
            )
        ).all()
    )

    # --- Agenda: concluídas/canceladas no período e próximas ---
    appt_status = dict(
        (
            await session.execute(
                select(Appointment.status, func.count())
                .where(
                    Appointment.tenant_id == tid,
                    Appointment.scheduled_at >= period_start,
                    Appointment.scheduled_at < period_end,
                )
                .group_by(Appointment.status)
            )
        ).all()
    )
    appointments_completed = appt_status.get(AppointmentStatus.COMPLETED, 0)
    appointments_cancelled = appt_status.get(AppointmentStatus.CANCELLED, 0)
    appointments_upcoming = (
        await session.execute(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.tenant_id == tid,
                Appointment.status.in_(_OPEN),
                Appointment.scheduled_at >= now,
            )
        )
    ).scalar_one()

    completed_by_doctor = dict(
        (
            await session.execute(
                select(Appointment.doctor_id, func.count())
                .where(
                    Appointment.tenant_id == tid,
                    Appointment.status == AppointmentStatus.COMPLETED,
                    Appointment.scheduled_at >= period_start,
                    Appointment.scheduled_at < period_end,
                )
                .group_by(Appointment.doctor_id)
            )
        ).all()
    )

    # --- Financeiro: recebido × a receber no período, total e por médico ---
    charges = list(
        (
            await session.execute(
                select(ConsultationCharge).where(
                    ConsultationCharge.tenant_id == tid,
                    ConsultationCharge.created_at >= period_start,
                    ConsultationCharge.created_at < period_end,
                )
            )
        )
        .scalars()
        .all()
    )
    received_cents = 0
    to_receive_cents = 0
    received_by_doctor: dict[uuid.UUID, int] = {}
    to_receive_by_doctor: dict[uuid.UUID, int] = {}
    for c in charges:
        if c.status in ("cancelled", "denied"):
            continue
        if c.status == "received":
            received_cents += c.doctor_cents
            received_by_doctor[c.doctor_id] = received_by_doctor.get(c.doctor_id, 0) + c.doctor_cents
        else:  # pending / billed
            to_receive_cents += c.doctor_cents
            to_receive_by_doctor[c.doctor_id] = to_receive_by_doctor.get(c.doctor_id, 0) + c.doctor_cents

    # --- Comparativo por médico ---
    doctors = list(
        (await session.execute(select(Doctor).where(Doctor.tenant_id == tid))).scalars().all()
    )
    doctor_stats = [
        DoctorStat(
            doctor_id=d.id,
            name=d.name,
            patients=pt_by_doctor.get(d.id, 0),
            appointments_completed=completed_by_doctor.get(d.id, 0),
            received_cents=received_by_doctor.get(d.id, 0),
            to_receive_cents=to_receive_by_doctor.get(d.id, 0),
        )
        for d in doctors
    ]
    doctor_stats.sort(key=lambda s: s.received_cents + s.to_receive_cents, reverse=True)

    attention = await compute_attention(session, tenant_id=tid)

    return ClinicDashboard(
        period_start=period_start,
        period_end=period_end,
        patients_total=patients_total,
        doctors_total=len(doctors),
        risk=risk,
        attention_count=len(attention),
        appointments_upcoming=appointments_upcoming,
        appointments_completed=appointments_completed,
        appointments_cancelled=appointments_cancelled,
        received_cents=received_cents,
        to_receive_cents=to_receive_cents,
        doctors=doctor_stats,
    )
