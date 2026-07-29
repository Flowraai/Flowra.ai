"""Dependências de autenticação/autorização, separadas por perfil (seção 7)."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token, hash_patient_token
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import UserRole
from app.models.patient import Patient
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
