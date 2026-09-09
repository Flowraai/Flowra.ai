"""Testes de receita (rascunho, emissão via provedor interno, renovação)."""

from __future__ import annotations

import httpx

ITEMS = [{"name": "Sertralina", "dose": "50mg", "instructions": "1x ao dia", "times": []}]


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5511999999999", "consent_given": True})).json()


async def _prescription(client: httpx.AsyncClient, headers: dict, patient_id: str) -> dict:
    return (await client.post(f"/api/v1/patients/{patient_id}/prescriptions", headers=headers,
                              json={"items": ITEMS})).json()


async def test_create_issue_and_patient_sees(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    presc = await _prescription(client, headers, patient["id"])
    assert presc["status"] == "draft"

    ph = {"X-Patient-Token": patient["access_token"]}
    # rascunho não aparece para o paciente
    assert (await client.get("/api/v1/patient/prescriptions", headers=ph)).json() == []

    r = await client.post(f"/api/v1/prescriptions/{presc['id']}/issue", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "issued"
    assert r.json()["external_id"].startswith("internal:")
    assert r.json()["issued_at"] is not None

    mine = (await client.get("/api/v1/patient/prescriptions", headers=ph)).json()
    assert len(mine) == 1 and mine[0]["items"][0]["name"] == "Sertralina"


async def test_issue_only_draft(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    presc = await _prescription(client, headers, patient["id"])
    await client.post(f"/api/v1/prescriptions/{presc['id']}/issue", headers=headers)
    # segunda emissão falha (não é mais rascunho)
    again = await client.post(f"/api/v1/prescriptions/{presc['id']}/issue", headers=headers)
    assert again.status_code == 409


async def test_renew_creates_draft(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    presc = await _prescription(client, headers, patient["id"])
    await client.post(f"/api/v1/prescriptions/{presc['id']}/issue", headers=headers)

    r = await client.post(f"/api/v1/prescriptions/{presc['id']}/renew", headers=headers)
    assert r.status_code == 201
    assert r.json()["status"] == "draft"
    assert r.json()["id"] != presc["id"]
    assert r.json()["items"] == ITEMS


async def test_cancel(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    presc = await _prescription(client, headers, patient["id"])
    r = await client.post(f"/api/v1/prescriptions/{presc['id']}/cancel", headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"


async def test_prescription_isolation(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient(client, headers_a)
    presc = await _prescription(client, headers_a, patient["id"])
    headers_b = await _doctor(client, email="dr.b@x.com")
    r = await client.get(f"/api/v1/prescriptions/{presc['id']}", headers=headers_b)
    assert r.status_code == 404


async def test_issue_creates_medication_plan_for_items_with_times(client: httpx.AsyncClient):
    """Item com horário vira plano de medicação (lembrete + adesão) ao emitir."""
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    presc = (await client.post(
        f"/api/v1/patients/{patient['id']}/prescriptions", headers=headers,
        json={"items": [
            {"name": "Quetiapina", "dose": "25mg", "times": ["22:00"]},   # com horário
            {"name": "Rivotril", "dose": "0,5mg", "times": []},           # sem horário (PRN)
        ]},
    )).json()

    # Antes de emitir, nenhum plano criado.
    meds0 = (await client.get(f"/api/v1/patients/{patient['id']}/medications", headers=headers)).json()
    assert meds0 == []

    await client.post(f"/api/v1/prescriptions/{presc['id']}/issue", headers=headers)

    meds = (await client.get(f"/api/v1/patients/{patient['id']}/medications", headers=headers)).json()
    assert len(meds) == 1  # só o item com horário
    plan = meds[0]
    assert plan["name"] == "Quetiapina" and plan["dose"] == "25mg"
    assert plan["times"] == ["22:00"] and plan["active"] is True


async def test_prescription_rejects_invalid_time(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    r = await client.post(
        f"/api/v1/patients/{patient['id']}/prescriptions", headers=headers,
        json={"items": [{"name": "X", "dose": "1mg", "times": ["25:99"]}]},
    )
    assert r.status_code == 422
