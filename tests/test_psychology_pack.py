"""Fluxo de psicologia: especialidade sem medicação, check-in e escalas."""

from __future__ import annotations

import httpx


async def _psychologist(client: httpx.AsyncClient, email: str = "psi@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Psi"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # Define a especialidade como psicologia.
    await client.patch("/api/v1/auth/me", headers=headers, json={"specialty": "psicologia"})
    return headers


async def test_care_info_and_specialties(client: httpx.AsyncClient):
    headers = await _psychologist(client)
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["care"]["specialty"] == "psicologia"
    assert me["care"]["label"] == "Psicologia"
    assert me["care"]["features"]["medicacao"] is False

    opts = (await client.get("/api/v1/auth/care/specialties", headers=headers)).json()
    keys = {o["key"] for o in opts}
    assert "psicologia" in keys and "psiquiatria" in keys


async def test_patient_protocol_has_no_medication_question(client: httpx.AsyncClient):
    headers = await _psychologist(client)
    patient = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "Cliente", "contact": "+5543988580825", "consent_given": True})).json()
    ph = {"X-Patient-Token": patient["access_token"]}

    proto = (await client.get("/api/v1/patient/protocol", headers=ph)).json()
    codes = {q["code"] for q in proto["questions"]}
    assert "medication_taken" not in codes and "side_effects" not in codes
    assert "mood" in codes and "self_harm" in codes  # o núcleo de saúde mental fica


async def test_scales_catalog_available(client: httpx.AsyncClient):
    headers = await _psychologist(client)
    cat = (await client.get("/api/v1/scales", headers=headers)).json()
    assert {s["code"] for s in cat} == {"phq9", "gad7"}


_STABLE = {"mood": 8, "anxiety": 2, "slept_well": "sim", "sleep_hours": 8,
           "crisis": "nao", "self_harm": "nao"}


async def _new_patient(client, headers, contact) -> dict:
    p = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "Cliente", "contact": contact, "consent_given": True})).json()
    return {"X-Patient-Token": p["access_token"]}


async def test_psychology_checkin_succeeds_without_medication(client: httpx.AsyncClient):
    headers = await _psychologist(client)
    ph = await _new_patient(client, headers, "+5543988580825")
    r = await client.post("/api/v1/patient/checkins", headers=ph, json={"structured_responses": _STABLE})
    assert r.status_code in (200, 201)
    assert (await client.get("/api/v1/patient/today", headers=ph)).json()["checked_in_today"] is True


async def test_medication_code_rejected_in_psychology(client: httpx.AsyncClient):
    headers = await _psychologist(client)
    ph = await _new_patient(client, headers, "+5543988580826")
    # medicação não existe no protocolo de psicologia → código desconhecido (422).
    bad = await client.post("/api/v1/patient/checkins", headers=ph,
                            json={"structured_responses": {**_STABLE, "medication_taken": "nao"}})
    assert bad.status_code == 422


async def test_selfharm_forces_alert_in_psychology(client: httpx.AsyncClient):
    headers = await _psychologist(client)
    ph = await _new_patient(client, headers, "+5543988580827")
    await client.post("/api/v1/patient/checkins", headers=ph,
                      json={"structured_responses": {**_STABLE, "self_harm": "sim"}})
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert any(a["urgency"] == "immediate" for a in alerts)
