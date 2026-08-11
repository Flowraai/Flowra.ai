"""Testes dos direitos do titular (LGPD): exportação e exclusão de dados."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.attachment import Attachment
from app.models.audit import AuditLog
from app.models.checkin import CheckIn
from app.models.enums import AuditAction
from app.models.notification import Notification
from app.services.storage import get_storage_backend

CRITICAL = {
    "mood": 1, "anxiety": 9, "slept_well": "nao", "sleep_hours": 2,
    "medication_taken": "nao", "crisis": "sim", "side_effects": "sim", "self_harm": "nao",
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


async def test_delete_removes_attachment_bytes_from_storage(client: httpx.AsyncClient):
    # LGPD-3 — a exclusão do paciente também precisa apagar os BYTES dos anexos
    # (áudios/imagens clínicas), não só as linhas no banco. Antes do fix, o
    # storage.delete() nunca era chamado e os arquivos ficavam órfãos no disco.
    headers = await _register(client)
    patient = (await client.post("/api/v1/patients", headers=headers,
                                 json={"name": "João", "consent_given": True})).json()
    pid = uuid.UUID(patient["id"])
    ph = {"X-Patient-Token": patient["access_token"]}
    await client.post("/api/v1/patient/attachments", headers=ph,
                      files={"file": ("voz.m4a", b"fake-audio-bytes", "audio/mp4")})

    # a chave de storage do anexo (não exposta pela API) + os bytes existem
    async with AsyncSessionLocal() as session:
        key = await session.scalar(
            select(Attachment.storage_key).where(Attachment.patient_id == pid))
    assert key is not None
    assert get_storage_backend().load(key) is not None

    resp = await client.delete(f"/api/v1/patients/{patient['id']}", headers=headers)
    assert resp.status_code == 204

    # os bytes sumiram do storage (não só a linha do banco)
    assert get_storage_backend().load(key) is None


async def test_ai_consent_defaults_off_and_is_settable(client: httpx.AsyncClient):
    # LGPD-4 — consentimento de IA externa é separado, começa DESLIGADO e o médico
    # registra/revoga. Sem ele, o sistema nunca manda texto/áudio a terceiros.
    headers = await _register(client)
    p = (await client.post("/api/v1/patients", headers=headers,
                           json={"name": "João", "consent_given": True})).json()
    assert p["ai_consent"] is False  # off por padrão

    on = await client.patch(f"/api/v1/patients/{p['id']}", headers=headers,
                            json={"ai_consent": True})
    assert on.status_code == 200 and on.json()["ai_consent"] is True

    off = await client.patch(f"/api/v1/patients/{p['id']}", headers=headers,
                             json={"ai_consent": False})
    assert off.json()["ai_consent"] is False


async def test_viewing_patient_record_is_audited(client: httpx.AsyncClient):
    # LGPD-5 — abrir o prontuário registra quem viu quem (accountability), sem
    # conteúdo clínico (só IDs).
    headers = await _register(client)
    patient = await _create_patient_with_checkin(client, headers)
    pid = uuid.UUID(patient["id"])

    r = await client.get(f"/api/v1/patients/{patient['id']}", headers=headers)
    assert r.status_code == 200

    async with AsyncSessionLocal() as session:
        viewed = await session.scalar(
            select(func.count()).select_from(AuditLog)
            .where(AuditLog.action == AuditAction.PATIENT_VIEWED,
                   AuditLog.entity_id == pid))
    assert viewed >= 1


async def test_cannot_delete_other_doctors_patient(client: httpx.AsyncClient):
    headers_a = await _register(client)
    patient = await _create_patient_with_checkin(client, headers_a)
    headers_b = await _register(client, email="dr.b@x.com")

    resp = await client.delete(f"/api/v1/patients/{patient['id']}", headers=headers_b)
    assert resp.status_code == 404
