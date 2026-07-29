"""Testes da detecção de não-adesão (paciente sem check-in)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.db.session import AsyncSessionLocal
from app.models.patient import Patient
from app.services.inactivity_service import days_since_checkin, is_inactive


# ---------- Unitário ----------
def _patient(last_checkin_days_ago: int | None, created_days_ago: int = 0) -> Patient:
    now = datetime.now(timezone.utc)
    return Patient(
        name="X",
        doctor_id=uuid.uuid4(),
        created_at=now - timedelta(days=created_days_ago),
        last_checkin_at=(now - timedelta(days=last_checkin_days_ago))
        if last_checkin_days_ago is not None
        else None,
    )


def test_days_since_checkin_uses_last_checkin():
    assert days_since_checkin(_patient(3)) == 3


def test_days_since_checkin_falls_back_to_created():
    assert days_since_checkin(_patient(None, created_days_ago=4)) == 4


def test_recent_patient_is_active():
    assert is_inactive(_patient(0)) is False


def test_old_patient_is_inactive():
    assert is_inactive(_patient(5)) is True


# ---------- Integração ----------
async def _register_patient(client: httpx.AsyncClient) -> tuple[dict, str]:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    p = await client.post("/api/v1/patients", headers=headers,
                          json={"name": "João", "consent_given": True})
    return headers, p.json()["id"]


async def test_scan_creates_alert_for_inactive_patient(client: httpx.AsyncClient):
    headers, patient_id = await _register_patient(client)

    # paciente recém-criado não é inativo: scan não cria nada
    first = await client.post("/api/v1/patients/scan-inactivity", headers=headers)
    assert first.status_code == 200 and first.json() == []

    # envelhece o último check-in no banco
    async with AsyncSessionLocal() as session:
        patient = await session.get(Patient, uuid.UUID(patient_id))
        patient.last_checkin_at = datetime.now(timezone.utc) - timedelta(days=5)
        await session.commit()

    # agora o scan gera um alerta de inatividade
    scan = await client.post("/api/v1/patients/scan-inactivity", headers=headers)
    assert scan.status_code == 200
    assert len(scan.json()) == 1
    assert scan.json()[0]["urgency"] == "routine"

    # painel reflete inatividade
    panel = (await client.get("/api/v1/patients", headers=headers)).json()
    assert panel[0]["inactive"] is True
    assert panel[0]["days_since_checkin"] >= 5
    assert panel[0]["open_alerts"] == 1

    # idempotente: não duplica alerta em aberto
    again = await client.post("/api/v1/patients/scan-inactivity", headers=headers)
    assert again.status_code == 200 and again.json() == []
