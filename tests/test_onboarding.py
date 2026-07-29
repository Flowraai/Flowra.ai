"""Testes de onboarding do paciente e notificações reais (destino/teste)."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.enums import AuditAction
from app.services.onboarding_service import build_onboarding_link


# ---------- Unitário ----------
def test_build_link_with_base(monkeypatch):
    monkeypatch.setattr(settings, "patient_app_url_base", "https://app.flowra/checkin")
    assert build_onboarding_link("abc") == "https://app.flowra/checkin?token=abc"


def test_build_link_without_base(monkeypatch):
    monkeypatch.setattr(settings, "patient_app_url_base", None)
    assert build_onboarding_link("abc") == "Token de acesso: abc"


# ---------- Onboarding no cadastro ----------
async def _doctor_headers(client: httpx.AsyncClient, **extra) -> dict:
    body = {"email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"}
    body.update(extra)
    r = await client.post("/api/v1/auth/register", json=body)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _onboarding_audits(patient_id: str) -> int:
    async with AsyncSessionLocal() as session:
        return await session.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == AuditAction.PATIENT_ONBOARDING_SENT,
                AuditLog.entity_id == uuid.UUID(patient_id),
            )
        )


async def test_onboarding_sent_when_contact_present(client: httpx.AsyncClient):
    headers = await _doctor_headers(client)
    p = await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5511999999999", "consent_given": True})
    assert p.status_code == 201
    assert await _onboarding_audits(p.json()["id"]) == 1


async def test_onboarding_skipped_without_contact(client: httpx.AsyncClient):
    headers = await _doctor_headers(client)
    p = await client.post("/api/v1/patients", headers=headers, json={
        "name": "Sem Contato", "consent_given": True})
    assert p.status_code == 201
    assert await _onboarding_audits(p.json()["id"]) == 0


async def test_resend_onboarding_rotates_token_and_returns_link(client: httpx.AsyncClient):
    headers = await _doctor_headers(client)
    p = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5511999999999", "consent_given": True})).json()
    old_token = p["access_token"]

    r = await client.post(f"/api/v1/patients/{p['id']}/resend-onboarding", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["sent"] is True
    assert data["access_token"] != old_token
    assert data["onboarding_link"]

    # token antigo invalidado; novo funciona
    assert (await client.get("/api/v1/patient/protocol",
            headers={"X-Patient-Token": old_token})).status_code == 401
    assert (await client.get("/api/v1/patient/protocol",
            headers={"X-Patient-Token": data["access_token"]})).status_code == 200


# ---------- Notificações reais: destino e teste ----------
async def test_notification_test_endpoint(client: httpx.AsyncClient):
    headers = await _doctor_headers(client)
    r = await client.post("/api/v1/notifications/test", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["target"] == "dra.ana@clinica.com"  # e-mail de login (sem notification_email)
    assert data["results"]["log"] == "sent"


async def test_notification_target_uses_notification_email(client: httpx.AsyncClient):
    headers = await _doctor_headers(client, notification_email="alertas@clinica.com")
    r = await client.post("/api/v1/notifications/test", headers=headers)
    assert r.json()["target"] == "alertas@clinica.com"
