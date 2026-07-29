"""Lógica de sessão do médico: refresh tokens (com rotação) e reset de senha."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
)
from app.models.auth_tokens import PasswordResetToken, RefreshToken
from app.models.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def issue_token_pair(session: AsyncSession, user: User) -> tuple[str, str]:
    """Cria um access token (JWT) e um refresh token opaco (persistido como hash)."""
    access = create_access_token(str(user.id), {"role": user.role.value})
    raw_refresh = generate_opaque_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    return access, raw_refresh


async def rotate_refresh_token(
    session: AsyncSession, raw_refresh: str
) -> tuple[str, str] | None:
    """Valida e rotaciona o refresh token. Retorna novo par ou None se inválido."""
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh))
    )
    token = result.scalar_one_or_none()
    if token is None or token.revoked_at is not None or token.expires_at <= _now():
        return None

    user = await session.get(User, token.user_id)
    if user is None or not user.is_active:
        return None

    token.revoked_at = _now()  # rotação: o token usado é revogado
    return await issue_token_pair(session, user)


async def revoke_all_refresh_tokens(session: AsyncSession, user_id) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def create_password_reset(session: AsyncSession, user: User) -> str:
    raw = generate_opaque_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=_now() + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    return raw


async def reset_password(session: AsyncSession, raw_token: str, new_password: str) -> bool:
    """Aplica a nova senha se o token for válido; revoga sessões (refresh tokens)."""
    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(raw_token)
        )
    )
    token = result.scalar_one_or_none()
    if token is None or token.used_at is not None or token.expires_at <= _now():
        return False

    user = await session.get(User, token.user_id)
    if user is None:
        return False

    user.hashed_password = hash_password(new_password)
    token.used_at = _now()
    await revoke_all_refresh_tokens(session, user.id)
    return True
