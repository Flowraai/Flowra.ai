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
