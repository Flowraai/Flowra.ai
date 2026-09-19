"""Dependências de autenticação/autorização, separadas por perfil (seção 7)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import decode_access_token, hash_patient_token
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import ClinicRole, SubscriptionStatus, UserRole
from app.models.membership import Membership
from app.models.patient import Patient
from app.models.subscription import Subscription
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)
_patient_token_header = APIKeyHeader(name="X-Patient-Token", auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise _CREDENTIALS_EXC
    payload = decode_access_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise _CREDENTIALS_EXC
    subject = payload.get("sub")
    try:
        user_id = uuid.UUID(str(subject))
    except (ValueError, TypeError):
        raise _CREDENTIALS_EXC
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXC
    return user


async def get_current_doctor(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Doctor:
    if user.role is not UserRole.DOCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao perfil médico.",
        )
    result = await session.execute(select(Doctor).where(Doctor.user_id == user.id))
    doctor = result.scalar_one_or_none()
    if doctor is None:
        raise _CREDENTIALS_EXC
    return doctor


@dataclass
class CurrentMember:
    """Quem está logado, dentro de qual clínica (tenant) e com qual papel.

    `doctor` é None para papéis sem perfil clínico (recepção/financeiro).
    """

    user: User
    tenant_id: uuid.UUID
    role: ClinicRole
    doctor: Doctor | None

    @property
    def is_management(self) -> bool:
        """Vê o tenant inteiro (dono/financeiro)."""
        return self.role in (ClinicRole.OWNER, ClinicRole.FINANCE)

    @property
    def can_read_clinical(self) -> bool:
        """Pode ler dado clínico (evolução, risco). Recepção/financeiro não."""
        return self.role in (ClinicRole.OWNER, ClinicRole.DOCTOR)


async def get_current_member(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CurrentMember:
    """Resolve o vínculo do usuário com a clínica (Membership) e o papel.

    Hoje um usuário tem um único membership (conta solo); quando houver mais de
    uma clínica, entra um seletor de tenant. Sem membership ativo → 401.
    """
    membership = (
        await session.execute(
            select(Membership)
            .where(Membership.user_id == user.id, Membership.is_active.is_(True))
            .order_by(Membership.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if membership is None:
        raise _CREDENTIALS_EXC
    doctor = (
        await session.execute(
            select(Doctor).where(
                Doctor.user_id == user.id, Doctor.tenant_id == membership.tenant_id
            )
        )
    ).scalar_one_or_none()
    return CurrentMember(
        user=user, tenant_id=membership.tenant_id, role=membership.role, doctor=doctor
    )


def scope_query(stmt: Select, model, member: CurrentMember) -> Select:
    """Aplica o filtro de visibilidade por papel a uma query.

    Médico vê o que é dele (`doctor_id`); gestão/recepção veem o tenant inteiro
    (`tenant_id`). O corte de dado clínico (recepção não lê evolução) é feito na
    rota, via `can_read_clinical`.
    """
    if member.role is ClinicRole.DOCTOR and member.doctor is not None:
        return stmt.where(model.doctor_id == member.doctor.id)
    return stmt.where(model.tenant_id == member.tenant_id)


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Admin da plataforma (gestão de planos). Definido por ADMIN_EMAILS."""
    if not settings.is_admin_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao administrador da plataforma.",
        )
    return user


def _subscription_grants_access(sub: Subscription) -> bool:
    now = datetime.now(timezone.utc)
    if sub.status is SubscriptionStatus.ACTIVE:
        return sub.current_period_end is None or sub.current_period_end >= now
    if sub.status is SubscriptionStatus.TRIALING:
        return sub.trial_end is None or sub.trial_end >= now
    return False


async def require_active_subscription(
    user: User = Depends(get_current_user),
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Doctor:
    """Exige assinatura ativa do tenant para as telas clínicas.

    No-op quando BILLING_ENABLED=false (comportamento atual). Admins da
    plataforma são isentos. Sem assinatura válida, retorna 402 para o painel
    redirecionar à tela de planos.
    """
    if not settings.billing_enabled or settings.is_admin_email(user.email):
        return doctor
    result = await session.execute(
        select(Subscription).where(Subscription.tenant_id == doctor.tenant_id)
    )
    sub = result.scalar_one_or_none()
    if sub is not None and _subscription_grants_access(sub):
        return doctor
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail="Assinatura necessária para acessar o painel.",
    )


async def get_current_patient(
    token: str | None = Depends(_patient_token_header),
    session: AsyncSession = Depends(get_db),
) -> Patient:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de paciente ausente.",
        )
    token_hash = hash_patient_token(token)
    result = await session.execute(
        select(Patient)
        .where(Patient.access_token_hash == token_hash)
        .options(selectinload(Patient.active_protocol))
    )
    patient = result.scalar_one_or_none()
    if patient is None or not patient.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de paciente inválido.",
        )
    return patient
