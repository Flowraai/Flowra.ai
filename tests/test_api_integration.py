"""Testes de integração da API contra Postgres real (fluxo do MVP).

Cobrem o caminho ponta a ponta descrito no planejamento: cadastro do médico,
consentimento LGPD, emissão de token do paciente, protocolo do dia, check-in
com cálculo de risco, geração de alerta, painel priorizado e isolamento entre
médicos.
"""

from __future__ import annotations

import httpx

from app.models.enums import RiskLevel
from tests.factories import insert_checkin

STABLE = {
    "mood": 8, "anxiety": 2, "slept_well": "sim", "sleep_hours": 8,
    "medication_taken": "sim", "crisis": "nao", "side_effects": "nao",
}
CRITICAL = {
    "mood": 1, "anxiety": 9, "slept_well": "nao", "sleep_hours": 2,
    "medication_taken": "nao", "crisis": "sim", "side_effects": "sim",
}


async def _register_doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana",
        "specialty": "psiquiatria", "council_id": "CRM-SP 12345"})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_patient(client: httpx.AsyncClient, headers: dict) -> dict:
    resp = await client.post("/api/v1/patients", headers=headers, json={
        "name": "João Silva", "contact": "+5511999999999",
        "consent_given": True, "consent_version": "v1"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_register_and_login(client: httpx.AsyncClient):
    await _register_doctor(client)
    resp = await client.post("/api/v1/auth/login", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123"})
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"

    wrong = await client.post("/api/v1/auth/login", json={
        "email": "dra.ana@clinica.com", "password": "errada"})
    assert wrong.status_code == 401


async def test_duplicate_email_conflict(client: httpx.AsyncClient):
    await _register_doctor(client)
    resp = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "outrasenha123", "name": "Outra"})
    assert resp.status_code == 409


async def test_patient_requires_lgpd_consent(client: httpx.AsyncClient):
    headers = await _register_doctor(client)
    resp = await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "consent_given": False})
    assert resp.status_code == 400


async def test_patient_creation_assigns_protocol_and_token(client: httpx.AsyncClient):
    headers = await _register_doctor(client)
    patient = await _create_patient(client, headers)
    assert patient["current_risk"] == "green"
    assert patient["active_protocol_id"]
    assert patient["access_token"]
    assert patient["consent_given_at"]


async def test_patient_fetches_daily_protocol(client: httpx.AsyncClient):
    headers = await _register_doctor(client)
    patient = await _create_patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    resp = await client.get("/api/v1/patient/protocol", headers=ph)
    assert resp.status_code == 200
    assert len(resp.json()["questions"]) == 8


async def test_invalid_patient_token_rejected(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/patient/protocol", headers={"X-Patient-Token": "nope"})
    assert resp.status_code == 401


async def test_stable_checkin_stays_green_without_alert(client: httpx.AsyncClient):
    headers = await _register_doctor(client)
    patient = await _create_patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    resp = await client.post("/api/v1/patient/checkins", headers=ph,
                             json={"structured_responses": STABLE})
    assert resp.status_code == 201

    panel = (await client.get("/api/v1/patients", headers=headers)).json()
    assert panel[0]["current_risk"] == "green"
    assert panel[0]["open_alerts"] == 0
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert alerts == []


async def test_critical_checkin_triggers_red_and_immediate_alert(client: httpx.AsyncClient):
    headers = await _register_doctor(client)
    patient = await _create_patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    resp = await client.post("/api/v1/patient/checkins", headers=ph, json={
        "structured_responses": CRITICAL,
        "free_text": "não aguento mais viver assim"})
    assert resp.status_code == 201
    # Retorno ao paciente é neutro: não expõe o risco calculado.
    assert "risco" not in resp.json()["message"].lower()

    panel = (await client.get("/api/v1/patients", headers=headers)).json()
    assert panel[0]["current_risk"] == "red"
    assert panel[0]["open_alerts"] == 1

    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert len(alerts) == 1
    assert alerts[0]["urgency"] == "immediate"
    assert alerts[0]["reasons_detail"]


async def test_panel_orders_by_risk(client: httpx.AsyncClient):
    headers = await _register_doctor(client)
    # paciente estável
    p_stable = await _create_patient(client, headers)
    await client.post("/api/v1/patient/checkins",
                      headers={"X-Patient-Token": p_stable["access_token"]},
                      json={"structured_responses": STABLE})
    # paciente crítico
    p_crit = await client.post("/api/v1/patients", headers=headers, json={
        "name": "Maria", "consent_given": True})
    p_crit = p_crit.json()
    await client.post("/api/v1/patient/checkins",
                      headers={"X-Patient-Token": p_crit["access_token"]},
                      json={"structured_responses": CRITICAL})

    panel = (await client.get("/api/v1/patients", headers=headers)).json()
    assert panel[0]["current_risk"] == "red"      # crítico primeiro
    assert panel[-1]["current_risk"] == "green"


async def test_alert_status_update(client: httpx.AsyncClient):
    headers = await _register_doctor(client)
    patient = await _create_patient(client, headers)
    await client.post("/api/v1/patient/checkins",
                      headers={"X-Patient-Token": patient["access_token"]},
                      json={"structured_responses": CRITICAL})
    alert = (await client.get("/api/v1/alerts", headers=headers)).json()[0]

    resp = await client.patch(f"/api/v1/alerts/{alert['id']}", headers=headers,
                              json={"status": "resolved"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"

    open_alerts = (await client.get("/api/v1/alerts?status_filter=pending", headers=headers)).json()
    assert open_alerts == []


async def test_checkin_history(client: httpx.AsyncClient):
    headers = await _register_doctor(client)
    patient = await _create_patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    # check-in de ontem (verde) + check-in de hoje (crítico) — um por dia.
    await insert_checkin(patient["id"], risk_level=RiskLevel.GREEN, days_ago=1)
    await client.post("/api/v1/patient/checkins", headers=ph, json={"structured_responses": CRITICAL})

    history = (await client.get(f"/api/v1/patients/{patient['id']}/checkins", headers=headers)).json()
    assert len(history) == 2
    assert history[0]["risk_level"] == "red"  # mais recente primeiro


async def test_doctor_isolation(client: httpx.AsyncClient):
    headers_a = await _register_doctor(client)
    patient = await _create_patient(client, headers_a)
    headers_b = await _register_doctor(client, email="dr.b@x.com")

    resp = await client.get(f"/api/v1/patients/{patient['id']}", headers=headers_b)
    assert resp.status_code == 404


async def test_token_rotation_invalidates_old_token(client: httpx.AsyncClient):
    headers = await _register_doctor(client)
    patient = await _create_patient(client, headers)
    old_token = patient["access_token"]

    rotated = await client.post(f"/api/v1/patients/{patient['id']}/rotate-token", headers=headers)
    assert rotated.status_code == 200
    new_token = rotated.json()["access_token"]
    assert new_token != old_token

    old = await client.get("/api/v1/patient/protocol", headers={"X-Patient-Token": old_token})
    assert old.status_code == 401
    new = await client.get("/api/v1/patient/protocol", headers={"X-Patient-Token": new_token})
    assert new.status_code == 200
