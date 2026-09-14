"""Vertical de Nutrição: 4º pacote clínico."""

from __future__ import annotations

import httpx


async def _nutritionist(client: httpx.AsyncClient, email: str = "nutri@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Nutri",
        "specialty": "nutricao"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client, headers, contact="+5543988580840") -> dict:
    p = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "Paciente", "contact": contact, "consent_given": True})).json()
    return {"X-Patient-Token": p["access_token"]}


async def test_registered_and_features(client: httpx.AsyncClient):
    headers = await _nutritionist(client)
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["care"]["specialty"] == "nutricao" and me["care"]["label"] == "Nutrição"
    assert me["care"]["features"]["medicacao"] is False  # nutricionista não prescreve remédio
    opts = (await client.get("/api/v1/auth/care/specialties")).json()
    assert "nutricao" in {o["key"] for o in opts}


async def test_protocol_is_nutritional(client: httpx.AsyncClient):
    headers = await _nutritionist(client)
    ph = await _patient(client, headers)
    proto = (await client.get("/api/v1/patient/protocol", headers=ph)).json()
    codes = {q["code"] for q in proto["questions"]}
    assert {"meal_plan", "gi_symptoms", "binge"} <= codes
    assert "mood" not in codes and "self_harm" not in codes


async def test_binge_and_offplan_generate_signal(client: httpx.AsyncClient):
    headers = await _nutritionist(client)
    ph = await _patient(client, headers, "+5543988580841")
    resp = {"meal_plan": "nao", "gi_symptoms": "nenhum", "binge": "sim"}
    r = await client.post("/api/v1/patient/checkins", headers=ph, json={"structured_responses": resp})
    assert r.status_code in (200, 201)
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert any("compuls" in a["reason"].lower() for a in alerts)


async def test_free_text_crisis_is_analyzed(client: httpx.AsyncClient):
    # Nutrição mantém o analisador de crise ligado (comorbidade com saúde mental).
    headers = await _nutritionist(client)
    ph = await _patient(client, headers, "+5543988580842")
    resp = {"meal_plan": "sim", "gi_symptoms": "nenhum", "binge": "nao"}
    await client.post("/api/v1/patient/checkins", headers=ph,
                      json={"structured_responses": resp, "free_text": "não quero mais viver"})
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert any(a["urgency"] == "immediate" for a in alerts)
