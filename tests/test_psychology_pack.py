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


async def test_register_with_specialty(client: httpx.AsyncClient):
    # Especialidade escolhida já no cadastro (sem precisar editar depois).
    r = await client.post("/api/v1/auth/register", json={
        "email": "novo.psi@x.com", "password": "senhaforte123", "name": "Psi",
        "specialty": "psicologia"})
    assert r.status_code in (200, 201)
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["care"]["specialty"] == "psicologia" and me["care"]["features"]["medicacao"] is False


async def test_specialties_endpoint_is_public(client: httpx.AsyncClient):
    # O formulário de cadastro precisa da lista ANTES do login (sem token).
    r = await client.get("/api/v1/auth/care/specialties")
    assert r.status_code == 200
    keys = {o["key"] for o in r.json()}
    assert {"psiquiatria", "psicologia", "odontologia"} <= keys


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


async def test_today_exposes_features_for_app(client: httpx.AsyncClient):
    headers = await _psychologist(client)
    ph = await _new_patient(client, headers, "+5543988580828")
    today = (await client.get("/api/v1/patient/today", headers=ph)).json()
    # O app usa isto para esconder a aba Remédios em psicologia.
    assert today["features"]["medicacao"] is False


async def test_scales_catalog_includes_psychology_scales(client: httpx.AsyncClient):
    headers = await _psychologist(client)
    cat = (await client.get("/api/v1/scales", headers=headers)).json()
    assert {s["code"] for s in cat} == {"phq9", "gad7", "pss10", "who5"}
    who5 = next(s for s in cat if s["code"] == "who5")
    assert who5["higher_is_worse"] is False  # bem-estar: maior = melhor


async def test_psychiatry_catalog_unchanged(client: httpx.AsyncClient):
    # Psiquiatria (default) segue só com PHQ-9/GAD-7 — pss10/who5 são do pacote psi.
    r = await client.post("/api/v1/auth/register", json={
        "email": "dr.psiq@x.com", "password": "senhaforte123", "name": "Dr"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cat = (await client.get("/api/v1/scales", headers=headers)).json()
    assert {s["code"] for s in cat} == {"phq9", "gad7"}


async def test_apply_pss10_end_to_end(client: httpx.AsyncClient):
    headers = await _psychologist(client)
    patient = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "Cliente", "contact": "+5543988580829", "consent_given": True})).json()
    ph = {"X-Patient-Token": patient["access_token"]}
    req = (await client.post(f"/api/v1/patients/{patient['id']}/scales", headers=headers,
                             json={"scale_code": "pss10"})).json()
    res = await client.post(f"/api/v1/patient/scales/{req['id']}", headers=ph,
                            json={"answers": [4] * 10})
    assert res.status_code == 200
    done = (await client.get(f"/api/v1/patients/{patient['id']}/scales", headers=headers)).json()
    assert done[0]["score"] == 24 and done[0]["severity"] == "Moderado"


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
