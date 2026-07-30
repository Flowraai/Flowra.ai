"""Testes de CRUD de paciente/médico e do estado do dia do paciente."""

from __future__ import annotations

import httpx

STABLE = {
    "mood": 8, "anxiety": 2, "slept_well": "sim", "sleep_hours": 8,
    "medication_taken": "sim", "crisis": "nao", "side_effects": "nao",
}


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers,
                              json={"name": "João", "contact": "+5511999999999",
                                    "consent_given": True})).json()


# ---------- Paciente ----------
async def test_update_patient_fields(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)

    r = await client.patch(f"/api/v1/patients/{patient['id']}", headers=headers,
                           json={"name": "João Silva", "contact": "joao@x.com"})
    assert r.status_code == 200
    assert r.json()["name"] == "João Silva"
    assert r.json()["contact"] == "joao@x.com"


async def test_deactivate_patient_removes_from_panel_and_blocks_token(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)

    r = await client.patch(f"/api/v1/patients/{patient['id']}", headers=headers,
                           json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False

    # some do painel
    panel = (await client.get("/api/v1/patients", headers=headers)).json()
    assert all(p["id"] != patient["id"] for p in panel)

    # o token do paciente para de funcionar
    blocked = await client.get("/api/v1/patient/protocol",
                               headers={"X-Patient-Token": patient["access_token"]})
    assert blocked.status_code == 401


async def test_cannot_update_other_doctors_patient(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient(client, headers_a)
    headers_b = await _doctor(client, email="dr.b@x.com")

    r = await client.patch(f"/api/v1/patients/{patient['id']}", headers=headers_b,
                           json={"name": "Hack"})
    assert r.status_code == 404


# ---------- Estado do dia do paciente ----------
async def test_patient_today_reflects_checkin(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    before = await client.get("/api/v1/patient/today", headers=ph)
    assert before.status_code == 200
    assert before.json()["checked_in_today"] is False
    assert before.json()["patient_name"] == "João"

    await client.post("/api/v1/patient/checkins", headers=ph,
                      json={"structured_responses": STABLE})

    after = (await client.get("/api/v1/patient/today", headers=ph)).json()
    assert after["checked_in_today"] is True
    assert after["last_checkin_at"] is not None


# ---------- Médico ----------
async def test_update_doctor_profile(client: httpx.AsyncClient):
    headers = await _doctor(client)
    r = await client.patch("/api/v1/auth/me", headers=headers,
                           json={"clinic": "Clínica Central", "notification_phone": "+5511988887777"})
    assert r.status_code == 200
    assert r.json()["clinic"] == "Clínica Central"
    assert r.json()["notification_phone"] == "+5511988887777"

    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["clinic"] == "Clínica Central"
