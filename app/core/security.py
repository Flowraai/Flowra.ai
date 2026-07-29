"""Primitivas de segurança: hash de senha, hash de token de paciente e JWT do médico."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Senhas (perfil médico) ---
def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


# --- Token de acesso do paciente ---
# O paciente não usa senha no MVP: recebe um token opaco (via app/WhatsApp/link).
# Guardamos apenas o hash do token no banco; o token em claro é exibido uma única vez.
def generate_patient_token() -> str:
    return secrets.token_urlsafe(32)


def hash_patient_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
