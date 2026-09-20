"""Acesso ao paciente ciente da equipe de cuidado.

Um profissional acessa um paciente se é o responsável (patient.doctor_id) ou está
na equipe de cuidado dele. Gestão (dono) vê o tenant inteiro. Os REGISTROS clínicos
seguem por autor (cada um vê a sua parte) — isto aqui é só o portão do paciente.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember
from app.models.care_team import CareTeamMember
from app.models.enums import ClinicRole
from app.models.patient import Patient


def patient_visible_clause(member: CurrentMember) -> ColumnElement[bool]:
    """Cláusula SQL para filtrar Patient conforme o papel (responsável+equipe / tenant)."""
    if member.role is ClinicRole.DOCTOR and member.doctor is not None:
        return or_(
            Patient.doctor_id == member.doctor.id,
            Patient.id.in_(
                select(CareTeamMember.patient_id).where(
                    CareTeamMember.doctor_id == member.doctor.id
                )
            ),
        )
    return Patient.tenant_id == member.tenant_id


async def can_access_patient(
    session: AsyncSession, member: CurrentMember, patient: Patient | None
) -> bool:
    """O membro pode acessar este paciente (responsável, equipe de cuidado ou gestão)?"""
    if patient is None:
        return False
    if member.role is ClinicRole.DOCTOR and member.doctor is not None:
        if patient.doctor_id == member.doctor.id:
            return True
        found = await session.execute(
            select(
                exists().where(
                    CareTeamMember.patient_id == patient.id,
                    CareTeamMember.doctor_id == member.doctor.id,
                )
            )
        )
        return bool(found.scalar())
    return patient.tenant_id == member.tenant_id


async def can_access_resource(
    session: AsyncSession, member: CurrentMember, resource: object | None
) -> bool:
    """Acesso a um registro clínico = acesso ao paciente dele (equipe de cuidado)."""
    if resource is None:
        return False
    patient = await session.get(Patient, resource.patient_id)  # type: ignore[attr-defined]
    return await can_access_patient(session, member, patient)


def is_primary_or_manager(member: CurrentMember, patient: Patient) -> bool:
    """Ações administrativas do paciente (editar cadastro, excluir, token) — só o
    responsável ou a gestão, não qualquer membro da equipe."""
    if member.role is ClinicRole.DOCTOR and member.doctor is not None:
        return patient.doctor_id == member.doctor.id
    return patient.tenant_id == member.tenant_id
