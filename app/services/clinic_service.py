"""Equipe da clínica: criar convites e aceitá-los (vira Membership/Doctor)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember
from app.core.config import settings
from app.core.security import generate_opaque_token, hash_password, hash_token
from app.models.doctor import Doctor
from app.models.enums import ClinicRole, UserRole
from app.models.invitation import Invitation
from app.models.membership import Membership
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.clinic import InvitationAccept, InvitationCreate
from app.services import auth_service
from app.services.notifications import send_plain


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_invitation(
    session: AsyncSession, member: CurrentMember, data: InvitationCreate
) -> tuple[Invitation, str]:
    """Cria o convite e envia o e-mail com o link. Retorna (convite, token cru)."""
    email = data.email.lower()
    # Já é membro desta clínica?
    existing = (
        await session.execute(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(User.email == email, Membership.tenant_id == member.tenant_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Esse e-mail já faz parte da clínica."
        )

    raw = generate_opaque_token()
    invite = Invitation(
        tenant_id=member.tenant_id,
        email=email,
        role=ClinicRole(data.role),
        can_view_finance=data.can_view_finance,
        token_hash=hash_token(raw),
        expires_at=_now() + timedelta(hours=settings.invite_expire_hours),
        invited_by_user_id=member.user.id,
    )
    session.add(invite)
    await session.flush()

    tenant = await session.get(Tenant, member.tenant_id)
    clinic_name = tenant.name if tenant else "a clínica"
    link = (
        f"{settings.invite_url_base}?token={raw}"
        if settings.invite_url_base
        else f"Token do convite: {raw}"
    )
    await send_plain(
        target=email,
        subject="[Flowra Care] Convite para a equipe",
        body=(
            f"Você foi convidado(a) para {clinic_name} no Flowra Care "
            f"como {data.role}.\n\n{link}\n\n"
            f"O convite expira em {settings.invite_expire_hours // 24} dia(s)."
        ),
    )
    return invite, raw


async def accept_invitation(session: AsyncSession, data: InvitationAccept) -> User:
    """Valida o token e cria o vínculo (User se preciso, Membership e Doctor)."""
    invite = (
        await session.execute(
            select(Invitation).where(Invitation.token_hash == hash_token(data.token))
        )
    ).scalar_one_or_none()
    if invite is None or invite.accepted_at is not None or invite.expires_at < _now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Convite inválido ou expirado."
        )

    user = (
        await session.execute(select(User).where(User.email == invite.email))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=invite.email,
            hashed_password=hash_password(data.password),
            role=UserRole.DOCTOR,
        )
        session.add(user)
        await session.flush()

    # Já é membro deste tenant? (convite duplicado)
    already = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user.id, Membership.tenant_id == invite.tenant_id
            )
        )
    ).scalar_one_or_none()
    if already is not None:
        invite.accepted_at = _now()
        return user

    session.add(
        Membership(
            user_id=user.id,
            tenant_id=invite.tenant_id,
            role=invite.role,
            can_view_finance=invite.can_view_finance,
        )
    )
    # Papel médico ganha um perfil clínico (Doctor) no tenant, se ainda não tiver.
    if invite.role is ClinicRole.DOCTOR:
        has_doctor = (
            await session.execute(
                select(Doctor).where(
                    Doctor.user_id == user.id, Doctor.tenant_id == invite.tenant_id
                )
            )
        ).scalar_one_or_none()
        if has_doctor is None:
            session.add(Doctor(user_id=user.id, tenant_id=invite.tenant_id, name=data.name))

    invite.accepted_at = _now()
    return user


async def issue_tokens(session: AsyncSession, user: User) -> tuple[str, str]:
    return await auth_service.issue_token_pair(session, user)
