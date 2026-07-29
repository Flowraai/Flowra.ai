"""Testes dos direitos do titular (LGPD): exportação e exclusão de dados."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.checkin import CheckIn
from app.models.enums import AuditAction
from app.models.notification import Notification

CRITICAL = {
    "mood": 1, "anxiety": 9, "slept_well": "nao", "sleep_hours": 2,
    "medication_taken": "nao", "crisis": "sim", "side_effects": "sim",
}


async def _register(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _create_patient_with_checkin(client: httpx.AsyncClient, headers: dict) -> dict:
    p = (await client.post("/api/v1/patients", headers=headers,
                           json={"name": "João", "consent_given": True})).json()
    await client.post("/api/v1/patient/checkins",
                      headers={"X-Patient-Token": p["access_token"]},
                      json={"structured_responses": CRITICAL})
    return p


# ---------- Exportação ----------
async def test_export_returns_full_data(client: httpx.AsyncClient):
    headers = await _register(client)
    patient = await _create_patient_with_checkin(client, headers)

    resp = await client.get(f"/api/v1/patients/{patient['id']}/export", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient"]["id"] == patient["id"]
    assert len(data["checkins"]) == 1
    assert len(data["alerts"]) == 1  # check-in crítico gerou alerta
    assert data["exported_at"]


async def test_cannot_export_other_doctors_patient(client: httpx.AsyncClient):
    headers_a = await _register(client)
    patient = await _create_patient_with_checkin(client, headers_a)
    headers_b = await _register(client, email="dr.b@x.com")

    resp = await client.get(f"/api/v1/patients/{patient['id']}/export", headers=headers_b)
    assert resp.status_code == 404


# ---------- Exclusão ----------
async def test_delete_erases_patient_and_health_data(client: httpx.AsyncClient):
    headers = await _register(client)
    patient = await _create_patient_with_checkin(client, headers)
    pid = uuid.UUID(patient["id"])

    resp = await client.delete(f"/api/v1/patients/{patient['id']}", headers=headers)
    assert resp.status_code == 204

    # paciente não existe mais
    assert (await client.get(f"/api/v1/patients/{patient['id']}",
            headers=headers)).status_code == 404
    # token do paciente deixa de funcionar
    assert (await client.get("/api/v1/patient/protocol",
            headers={"X-Patient-Token": patient["access_token"]})).status_code == 401

    async with AsyncSessionLocal() as session:
        # check-ins e notificações foram removidos por cascata
        checkins = await session.scalar(
            select(func.count()).select_from(CheckIn).where(CheckIn.patient_id == pid))
        notifs = await session.scalar(select(func.count()).select_from(Notification))
        assert checkins == 0 and notifs == 0
        # auditoria preservada: há registro de exclusão
        deleted = await session.scalar(
            select(func.count()).select_from(AuditLog)
            .where(AuditLog.action == AuditAction.PATIENT_DELETED,
                   AuditLog.entity_id == pid))
        assert deleted == 1


async def test_cannot_delete_other_doctors_patient(client: httpx.AsyncClient):
    headers_a = await _register(client)
    patient = await _create_patient_with_checkin(client, headers_a)
    headers_b = await _register(client, email="dr.b@x.com")

    resp = await client.delete(f"/api/v1/patients/{patient['id']}", headers=headers_b)
    assert resp.status_code == 404
