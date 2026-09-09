"""Login do paciente por CPF + senha: ativação, sessão e recuperação por código.

O token do convite é de PRIMEIRA ENTRADA: com ele o paciente define CPF + senha
(ativação). A partir daí, entra por CPF + senha e recebe um token de SESSÃO (o
mesmo mecanismo opaco X-Patient-Token, agora emitido no login). Recuperação de
senha é autosserviço: um código curto enviado ao contato (WhatsApp/e-mail).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_patient_token,
    hash_cpf,
    hash_password,
    hash_token,
    hash_patient_token,
)
from app.models.patient import Patient

RESET_CODE_TTL_MINUTES = 15


def mint_session_token(patient: Patient) -> str:
    """Emite um novo token de sessão (rotaciona o hash) e devolve o valor em claro."""
    raw = generate_patient_token()
    patient.access_token_hash = hash_patient_token(raw)
    return raw


async def cpf_in_use(session: AsyncSession, cpf_hash: str, exclude_id) -> bool:
    other = await session.scalar(
        select(Patient.id).where(
            Patient.cpf_hash == cpf_hash,
            Patient.id != exclude_id,
            Patient.password_hash.is_not(None),
        )
    )
    return other is not None


async def find_by_cpf(session: AsyncSession, cpf: str) -> Patient | None:
    """Paciente ATIVADO com este CPF (para login e recuperação)."""
    return await session.scalar(
        select(Patient).where(
            Patient.cpf_hash == hash_cpf(cpf),
            Patient.password_hash.is_not(None),
            Patient.is_active.is_(True),
        )
    )


def set_credentials(patient: Patient, cpf: str, password: str) -> None:
    patient.cpf_hash = hash_cpf(cpf)
    patient.password_hash = hash_password(password)
    patient.activated_at = datetime.now(timezone.utc)


def new_reset_code(patient: Patient) -> str:
    """Gera um código de 6 dígitos, guarda só o hash + validade, devolve em claro."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    patient.pwd_reset_code_hash = hash_token(code)
    patient.pwd_reset_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=RESET_CODE_TTL_MINUTES
    )
    return code


def check_reset_code(patient: Patient, code: str) -> bool:
    if not patient.pwd_reset_code_hash or not patient.pwd_reset_expires_at:
        return False
    if datetime.now(timezone.utc) > patient.pwd_reset_expires_at:
        return False
    return secrets.compare_digest(patient.pwd_reset_code_hash, hash_token(code.strip()))


def clear_reset_code(patient: Patient) -> None:
    patient.pwd_reset_code_hash = None
    patient.pwd_reset_expires_at = None
