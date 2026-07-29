"""Testes de idempotência do check-in e paginação das listas."""

from __future__ import annotations

import httpx

from app.models.enums import RiskLevel
from tests.factories import insert_checkin

STABLE = {
    "mood": 8, "anxiety": 2, "slept_well": "sim", "sleep_hours": 8,
    "medication_taken": "sim", "crisis": "nao", "side_effects": "nao",
}


async def _doctor(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict, name: str = "João") -> dict:
    return (await client.post("/api/v1/patients", headers=headers,
                              json={"name": name, "consent_given": True})).json()


# ---------- Idempotência ----------
async def test_second_checkin_same_day_is_rejected(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    first = await client.post("/api/v1/patient/checkins", headers=ph,
                              json={"structured_responses": STABLE})
    assert first.status_code == 201

    second = await client.post("/api/v1/patient/checkins", headers=ph,
                               json={"structured_responses": STABLE})
    assert second.status_code == 409


async def test_checkin_allowed_after_previous_day(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    # check-in de ontem não bloqueia o de hoje
    await insert_checkin(patient["id"], days_ago=1)
    r = await client.post("/api/v1/patient/checkins",
                          headers={"X-Patient-Token": patient["access_token"]},
                          json={"structured_responses": STABLE})
    assert r.status_code == 201


# ---------- Paginação ----------
async def test_panel_pagination(client: httpx.AsyncClient):
    headers = await _doctor(client)
    for i in range(3):
        await _patient(client, headers, name=f"P{i}")

    page1 = (await client.get("/api/v1/patients?limit=2&offset=0", headers=headers)).json()
    page2 = (await client.get("/api/v1/patients?limit=2&offset=2", headers=headers)).json()
    assert len(page1) == 2
    assert len(page2) == 1
    # sem sobreposição entre páginas
    assert {p["id"] for p in page1}.isdisjoint({p["id"] for p in page2})


async def test_checkins_pagination(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    for d in (1, 2, 3, 4):
        await insert_checkin(patient["id"], risk_level=RiskLevel.GREEN, days_ago=d)

    page1 = (await client.get(
        f"/api/v1/patients/{patient['id']}/checkins?limit=2&offset=0", headers=headers)).json()
    page2 = (await client.get(
        f"/api/v1/patients/{patient['id']}/checkins?limit=2&offset=2", headers=headers)).json()
    assert len(page1) == 2 and len(page2) == 2
    assert {c["id"] for c in page1}.isdisjoint({c["id"] for c in page2})


async def test_invalid_pagination_is_rejected(client: httpx.AsyncClient):
    headers = await _doctor(client)
    # limit fora do intervalo -> 422 (validação do Query)
    assert (await client.get("/api/v1/patients?limit=0", headers=headers)).status_code == 422
    assert (await client.get("/api/v1/patients?offset=-1", headers=headers)).status_code == 422
