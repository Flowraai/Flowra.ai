"""Testes do resumo do paciente (determinístico + LLM)."""

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


async def _patient_with_checkin(client: httpx.AsyncClient, headers: dict) -> dict:
    p = (await client.post("/api/v1/patients", headers=headers,
                           json={"name": "João", "consent_given": True})).json()
    await client.post("/api/v1/patient/checkins",
                      headers={"X-Patient-Token": p["access_token"]},
                      json={"structured_responses": STABLE})
    return p


async def test_deterministic_summary(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient_with_checkin(client, headers)

    r = await client.get(f"/api/v1/patients/{patient['id']}/summary", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["generated_by"] == "deterministic"  # sem chave de LLM no teste
    assert "João" in body["summary"]
    assert body["context"]["recent_checkins"] == 1


async def test_llm_summary(client: httpx.AsyncClient, monkeypatch):
    async def _fake(system: str, user: str, temperature: float = 0.2) -> str:
        return "Paciente estável, boa adesão."

    monkeypatch.setattr("app.services.summary_service.chat_complete", _fake)

    headers = await _doctor(client)
    patient = await _patient_with_checkin(client, headers)
    r = await client.get(f"/api/v1/patients/{patient['id']}/summary", headers=headers)
    assert r.status_code == 200
    assert r.json()["generated_by"] == "llm"
    assert r.json()["summary"] == "Paciente estável, boa adesão."


async def test_summary_isolation(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient_with_checkin(client, headers_a)
    headers_b = await _doctor(client, email="dr.b@x.com")
    r = await client.get(f"/api/v1/patients/{patient['id']}/summary", headers=headers_b)
    assert r.status_code == 404
