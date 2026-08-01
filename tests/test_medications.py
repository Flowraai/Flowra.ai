"""Testes de lembretes de medicação (planos, doses do dia, respostas, adesão)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers,
                              json={"name": "João", "consent_given": True})).json()


async def _plan(client: httpx.AsyncClient, headers: dict, patient_id: str,
                times=("08:00", "22:00")) -> dict:
    return (await client.post(f"/api/v1/patients/{patient_id}/medications", headers=headers,
                              json={"name": "Sertralina", "dose": "50mg",
                                    "times": list(times), "start_date": _today()})).json()


# ---------- Planos (médico) ----------
async def test_create_and_list_plan(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    plan = await _plan(client, headers, patient["id"])
    assert plan["name"] == "Sertralina" and plan["active"] is True

    plans = (await client.get(f"/api/v1/patients/{patient['id']}/medications",
                              headers=headers)).json()
    assert len(plans) == 1


async def test_invalid_times_rejected(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    r = await client.post(f"/api/v1/patients/{patient['id']}/medications", headers=headers,
                          json={"name": "X", "dose": "1", "times": ["25:00"],
                                "start_date": _today()})
    assert r.status_code == 422


async def test_plan_isolation(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient(client, headers_a)
    headers_b = await _doctor(client, email="dr.b@x.com")
    r = await client.post(f"/api/v1/patients/{patient['id']}/medications", headers=headers_b,
                          json={"name": "X", "dose": "1", "times": ["08:00"],
                                "start_date": _today()})
    assert r.status_code == 404


# ---------- Doses do dia (paciente) ----------
async def test_today_generates_doses(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    await _plan(client, headers, patient["id"], times=("08:00", "22:00"))
    ph = {"X-Patient-Token": patient["access_token"]}

    doses = (await client.get("/api/v1/patient/medications/today", headers=ph)).json()
    assert len(doses) == 2
    assert all(d["status"] == "pending" for d in doses)
    assert doses[0]["name"] == "Sertralina"


async def test_today_is_idempotent(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    await _plan(client, headers, patient["id"], times=("08:00", "22:00"))
    ph = {"X-Patient-Token": patient["access_token"]}

    first = (await client.get("/api/v1/patient/medications/today", headers=ph)).json()
    second = (await client.get("/api/v1/patient/medications/today", headers=ph)).json()
    assert len(first) == 2 and len(second) == 2
    assert {d["intake_id"] for d in first} == {d["intake_id"] for d in second}


async def test_deactivated_plan_generates_no_doses(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    plan = await _plan(client, headers, patient["id"])
    await client.patch(f"/api/v1/medications/{plan['id']}", headers=headers,
                       json={"active": False})
    ph = {"X-Patient-Token": patient["access_token"]}
    doses = (await client.get("/api/v1/patient/medications/today", headers=ph)).json()
    assert doses == []


# ---------- Resposta + adesão ----------
async def test_respond_and_adherence(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    await _plan(client, headers, patient["id"], times=("08:00", "22:00"))
    ph = {"X-Patient-Token": patient["access_token"]}

    doses = (await client.get("/api/v1/patient/medications/today", headers=ph)).json()
    intake_id = doses[0]["intake_id"]

    r = await client.post(f"/api/v1/patient/medications/intakes/{intake_id}/respond",
                          headers=ph, json={"status": "taken"})
    assert r.status_code == 200 and r.json()["status"] == "taken"
    assert r.json()["responded_at"] is not None

    adherence = (await client.get(
        f"/api/v1/patients/{patient['id']}/medications/adherence", headers=headers)).json()
    assert adherence["taken"] == 1
    assert adherence["adherence_rate"] == 1.0


async def test_respond_pending_is_rejected(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    await _plan(client, headers, patient["id"], times=("08:00",))
    ph = {"X-Patient-Token": patient["access_token"]}
    intake_id = (await client.get("/api/v1/patient/medications/today", headers=ph)).json()[0]["intake_id"]
    r = await client.post(f"/api/v1/patient/medications/intakes/{intake_id}/respond",
                          headers=ph, json={"status": "pending"})
    assert r.status_code == 422


async def test_cannot_respond_others_intake(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p1 = await _patient(client, headers)
    await _plan(client, headers, p1["id"], times=("08:00",))
    intake_id = (await client.get("/api/v1/patient/medications/today",
                 headers={"X-Patient-Token": p1["access_token"]})).json()[0]["intake_id"]

    # outro paciente tenta responder a tomada do primeiro
    p2 = (await client.post("/api/v1/patients", headers=headers,
                            json={"name": "Maria", "consent_given": True})).json()
    r = await client.post(f"/api/v1/patient/medications/intakes/{intake_id}/respond",
                          headers={"X-Patient-Token": p2["access_token"]},
                          json={"status": "taken"})
    assert r.status_code == 404
