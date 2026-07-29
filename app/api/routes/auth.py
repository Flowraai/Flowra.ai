"""Autenticação do perfil médico: registro e login (JWT)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import DoctorRegister, LoginRequest, Token
from app.schemas.doctor import DoctorProfile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_doctor(
    payload: DoctorRegister, session: AsyncSession = Depends(get_db)
) -> Token:
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
    await session.flush()

    doctor = Doctor(
        user_id=user.id,
        name=payload.name,
        specialty=payload.specialty,
        clinic=payload.clinic,
        council_id=payload.council_id,
    )
    session.add(doctor)

    return Token(access_token=create_access_token(str(user.id), {"role": user.role.value}))


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> Token:
    result = await session.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos."
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conta inativa.")
    return Token(access_token=create_access_token(str(user.id), {"role": user.role.value}))


@router.get("/me", response_model=DoctorProfile)
async def me(
    doctor: Doctor = Depends(get_current_doctor), session: AsyncSession = Depends(get_db)
) -> DoctorProfile:
    user = await session.get(User, doctor.user_id)
    return DoctorProfile(
        id=doctor.id,
        name=doctor.name,
        specialty=doctor.specialty,
        clinic=doctor.clinic,
        council_id=doctor.council_id,
        email=user.email,  # type: ignore[union-attr]
    )
