"""Primitivas de segurança: hash de senha, hash de token de paciente e JWT do médico."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# --- Senhas (perfil médico) ---
def _prehash_password(plain_password: str) -> bytes:
    """Normaliza a senha para caber no limite de 72 bytes do bcrypt.

    sha256 + base64 permite senhas de qualquer tamanho sem truncamento silencioso.
    """
    digest = hashlib.sha256(plain_password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(_prehash_password(plain_password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash_password(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        return False


# --- Tokens opacos (paciente, refresh, reset de senha) ---
# Guardamos apenas o hash no banco; o token em claro é exibido uma única vez.
def generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Aliases mantidos por clareza no domínio do paciente.
generate_patient_token = generate_opaque_token
hash_patient_token = hash_token


# --- CPF (login do paciente) ---
def normalize_cpf(cpf: str) -> str:
    """Mantém só os dígitos do CPF."""
    return "".join(ch for ch in cpf if ch.isdigit())


def valid_cpf(cpf: str) -> bool:
    """Valida CPF por dígitos verificadores (evita erro de digitação)."""
    d = normalize_cpf(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for i in (9, 10):  # calcula os dois dígitos verificadores
        s = sum(int(d[n]) * ((i + 1) - n) for n in range(i))
        check = (s * 10) % 11 % 10
        if check != int(d[i]):
            return False
    return True


def hash_cpf(cpf: str) -> str:
    """Hash determinístico do CPF (normalizado) para lookup — nunca guardamos em claro."""
    return hash_token(normalize_cpf(cpf))


# --- JWT (perfil médico) ---
def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
