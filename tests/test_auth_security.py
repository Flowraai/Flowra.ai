"""Testes de hardening: rate limiting, refresh token e reset de senha."""

from __future__ import annotations

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services import auth_service

EMAIL = "dra.ana@clinica.com"
PW = "senhaforte123"


async def _register(client: httpx.AsyncClient, email: str = EMAIL, pw: str = PW) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": pw, "name": "Dra. Ana"})
    assert r.status_code == 201, r.text
    return r.json()


# ---------- Token pair ----------
async def test_register_returns_access_and_refresh(client: httpx.AsyncClient):
    body = await _register(client)
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


# ---------- Rate limiting ----------
async def test_login_is_rate_limited(client: httpx.AsyncClient):
    await _register(client)
    limit = settings.login_rate_limit_attempts
    # tentativas com senha errada até o limite: todas 401
    for _ in range(limit):
        r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "errada"})
        assert r.status_code == 401
    # a próxima é bloqueada
    blocked = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PW})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


# ---------- Refresh token ----------
async def test_refresh_rotates_and_old_token_is_revoked(client: httpx.AsyncClient):
    body = await _register(client)
    old_refresh = body["refresh_token"]

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new = r.json()
    assert new["access_token"] and new["refresh_token"] != old_refresh

    # o refresh antigo foi revogado na rotação
    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401
    # o novo funciona
    again = await client.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]})
    assert again.status_code == 200


async def test_refresh_with_invalid_token_is_401(client: httpx.AsyncClient):
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": "nao-existe"})
    assert r.status_code == 401


# ---------- Reset de senha ----------
async def test_forgot_password_is_generic_for_any_email(client: httpx.AsyncClient):
    await _register(client)
    known = await client.post("/api/v1/auth/forgot-password", json={"email": EMAIL})
    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "ninguem@x.com"})
    assert known.status_code == 200 and unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]


async def _make_reset_token(email: str = EMAIL) -> str:
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        raw = await auth_service.create_password_reset(session, user)
        await session.commit()
    return raw


async def test_reset_password_changes_password_and_revokes_sessions(client: httpx.AsyncClient):
    body = await _register(client)
    old_refresh = body["refresh_token"]
    token = await _make_reset_token()

    new_pw = "novasenhaforte456"
    r = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": new_pw})
    assert r.status_code == 200

    # senha antiga não funciona mais; a nova sim
    assert (await client.post("/api/v1/auth/login",
            json={"email": EMAIL, "password": PW})).status_code == 401
    assert (await client.post("/api/v1/auth/login",
            json={"email": EMAIL, "password": new_pw})).status_code == 200

    # refresh tokens anteriores foram revogados
    assert (await client.post("/api/v1/auth/refresh",
            json={"refresh_token": old_refresh})).status_code == 401


async def test_reset_with_invalid_token_is_400(client: httpx.AsyncClient):
    await _register(client)
    r = await client.post("/api/v1/auth/reset-password",
                          json={"token": "invalido", "new_password": "outrasenha123"})
    assert r.status_code == 400


async def test_reset_token_is_single_use(client: httpx.AsyncClient):
    await _register(client)
    token = await _make_reset_token()
    first = await client.post("/api/v1/auth/reset-password",
                              json={"token": token, "new_password": "novasenha123"})
    assert first.status_code == 200
    second = await client.post("/api/v1/auth/reset-password",
                               json={"token": token, "new_password": "outrasenha789"})
    assert second.status_code == 400
