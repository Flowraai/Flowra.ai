"""Autenticação do perfil médico: registro, login, refresh e reset de senha."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import TenantKind, UserRole
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import (
    DoctorRegister,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
)
from app.schemas.doctor import DoctorProfile, DoctorUpdate
from app.services import auth_service
from app.services.notifications import send_plain

logger = logging.getLogger("flowra_care.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

_login_limit = rate_limit(
    settings.login_rate_limit_attempts, settings.login_rate_limit_window_seconds, "login"
)
_register_limit = rate_limit(
    settings.register_rate_limit_attempts, settings.login_rate_limit_window_seconds, "register"
)
_reset_limit = rate_limit(
    settings.password_reset_rate_limit_attempts,
    settings.login_rate_limit_window_seconds,
    "password_reset",
)


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_register_limit)],
)
async def register_doctor(
    payload: DoctorRegister, session: AsyncSession = Depends(get_db)
) -> TokenPair:
    existing = await session.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado."
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        role=UserRole.DOCTOR,
    )
    session.add(user)

    # Cada cadastro cria um tenant (a conta): clínica se houver nome de clínica,
    # senão profissional autônomo (solo).
    tenant = Tenant(
        name=payload.clinic or payload.name,
        kind=TenantKind.CLINIC if payload.clinic else TenantKind.SOLO,
    )
    session.add(tenant)
    await session.flush()

    session.add(
        Doctor(
            user_id=user.id,
            tenant_id=tenant.id,
            name=payload.name,
            specialty=payload.specialty,
            clinic=payload.clinic,
            council_id=payload.council_id,
            notification_email=payload.notification_email,
            notification_phone=payload.notification_phone,
        )
    )

    access, refresh = await auth_service.issue_token_pair(session, user)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenPair, dependencies=[Depends(_login_limit)])
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenPair:
    result = await session.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos."
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conta inativa.")
    access, refresh = await auth_service.issue_token_pair(session, user)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(_login_limit)])
async def refresh(payload: RefreshRequest, session: AsyncSession = Depends(get_db)) -> TokenPair:
    tokens = await auth_service.rotate_refresh_token(session, payload.refresh_token)
    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido ou expirado."
        )
    access, new_refresh = tokens
    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[Depends(_reset_limit)],
)
async def forgot_password(
    payload: ForgotPasswordRequest, session: AsyncSession = Depends(get_db)
) -> MessageResponse:
    # Resposta genérica: nunca revela se o e-mail existe (evita enumeração).
    generic = MessageResponse(
        message="Se o e-mail estiver cadastrado, enviaremos instruções de redefinição."
    )
    result = await session.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return generic

    raw = await auth_service.create_password_reset(session, user)
    link = (
        f"{settings.password_reset_url_base}?token={raw}"
        if settings.password_reset_url_base
        else f"Token de redefinição: {raw}"
    )
    await send_plain(
        target=user.email,
        subject="[Flowra Care] Redefinição de senha",
        body=(
            "Recebemos um pedido de redefinição de senha.\n\n"
            f"{link}\n\n"
            f"O link expira em {settings.password_reset_expire_minutes} minutos. "
            "Se não foi você, ignore este e-mail."
        ),
    )
    return generic


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest, session: AsyncSession = Depends(get_db)
) -> MessageResponse:
    ok = await auth_service.reset_password(session, payload.token, payload.new_password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido ou expirado."
        )
    return MessageResponse(message="Senha redefinida com sucesso. Faça login novamente.")


@router.get("/me", response_model=DoctorProfile)
async def me(
    doctor: Doctor = Depends(get_current_doctor), session: AsyncSession = Depends(get_db)
) -> DoctorProfile:
    return await _profile_response(session, doctor)


@router.patch("/me", response_model=DoctorProfile)
async def update_me(
    payload: DoctorUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> DoctorProfile:
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "name" and value is None:
            continue  # nome não pode ser nulo
        setattr(doctor, field, value)
    return await _profile_response(session, doctor)


async def _profile_response(session: AsyncSession, doctor: Doctor) -> DoctorProfile:
    user = await session.get(User, doctor.user_id)
    tenant = await session.get(Tenant, doctor.tenant_id)
    return DoctorProfile(
        id=doctor.id,
        tenant_id=doctor.tenant_id,
        tenant_name=tenant.name if tenant else None,
        name=doctor.name,
        specialty=doctor.specialty,
        clinic=doctor.clinic,
        council_id=doctor.council_id,
        notification_email=doctor.notification_email,
        notification_phone=doctor.notification_phone,
        email=user.email if user else "",
    )
