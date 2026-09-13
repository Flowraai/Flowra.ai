"""Painel "Quem precisa de atenção hoje": priorização e motivos."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.patient import Patient


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict, name: str = "João") -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": name, "contact": "+5543988580825", "consent_given": True})).json()


async def test_stable_patient_absent_from_attention(client: httpx.AsyncClient):
    headers = await _doctor(client)
    await _patient(client, headers)  # sem sinais → não aparece
    items = (await client.get("/api/v1/patients/attention", headers=headers)).json()
    assert items == []


async def test_flagged_scale_surfaces_patient_with_reason(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    req = (await client.post(f"/api/v1/patients/{patient['id']}/scales", headers=headers,
                             json={"scale_code": "phq9"})).json()
    # Item 9 = 2 sinaliza risco → escala flagged + alerta imediato.
    await client.post(f"/api/v1/patient/scales/{req['id']}", headers=ph,
                      json={"answers": [1, 1, 1, 1, 1, 1, 1, 1, 2]})

    items = (await client.get("/api/v1/patients/attention", headers=headers)).json()
    assert len(items) == 1
    it = items[0]
    assert it["id"] == patient["id"] and it["score"] > 0
    codes = {r["code"] for r in it["reasons"]}
    assert "scale" in codes  # escala sinalizada
    assert "alert" in codes  # o item 9 também gera alerta imediato
    assert any("PHQ-9" in r["label"] for r in it["reasons"] if r["code"] == "scale")


async def test_inactive_patient_flagged_and_ordering(client: httpx.AsyncClient):
    headers = await _doctor(client)
    # Paciente inativo (sem check-in há muito tempo).
    stale = await _patient(client, headers, name="Inativo")
    # Paciente com escala sinalizada (mais urgente).
    urgent = await _patient(client, headers, name="Urgente")
    ph = {"X-Patient-Token": urgent["access_token"]}
    req = (await client.post(f"/api/v1/patients/{urgent['id']}/scales", headers=headers,
                             json={"scale_code": "phq9"})).json()
    await client.post(f"/api/v1/patient/scales/{req['id']}", headers=ph,
                      json={"answers": [1, 1, 1, 1, 1, 1, 1, 1, 2]})

    async with AsyncSessionLocal() as s:
        p = await s.scalar(select(Patient).where(Patient.id == stale["id"]))
        p.last_checkin_at = datetime.now(timezone.utc) - timedelta(days=90)
        await s.commit()

    items = (await client.get("/api/v1/patients/attention", headers=headers)).json()
    ids = [i["id"] for i in items]
    assert stale["id"] in ids and urgent["id"] in ids
    # O paciente com alerta imediato + escala vem antes do só-inativo.
    assert ids.index(urgent["id"]) < ids.index(stale["id"])
    inactive_item = next(i for i in items if i["id"] == stale["id"])
    assert any(r["code"] == "inactive" for r in inactive_item["reasons"])


async def test_attention_isolated_per_doctor(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient(client, headers_a)
    ph = {"X-Patient-Token": patient["access_token"]}
    req = (await client.post(f"/api/v1/patients/{patient['id']}/scales", headers=headers_a,
                             json={"scale_code": "phq9"})).json()
    await client.post(f"/api/v1/patient/scales/{req['id']}", headers=ph,
                      json={"answers": [1, 1, 1, 1, 1, 1, 1, 1, 2]})
    headers_b = await _doctor(client, email="dr.b@x.com")
    assert (await client.get("/api/v1/patients/attention", headers=headers_b)).json() == []
