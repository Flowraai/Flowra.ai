"""Escalas clínicas (PHQ-9, GAD-7): pontuação, solicitação, resposta e alerta."""

from __future__ import annotations

import httpx

from app.clinical.scales import score_scale


def test_scoring():
    # PHQ-9 tudo 3 = 27, grave, item 9 sinaliza.
    assert score_scale("phq9", [3] * 9) == (27, "Grave", "red", True)
    # PHQ-9 leve, sem item 9.
    assert score_scale("phq9", [1, 1, 1, 1, 1, 0, 0, 0, 0]) == (5, "Leve", "yellow", False)
    # GAD-7 moderada.
    assert score_scale("gad7", [2, 2, 2, 2, 2, 1, 1]) == (12, "Moderada", "orange", False)


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5543988580825", "consent_given": True})).json()


async def test_catalog(client: httpx.AsyncClient):
    headers = await _doctor(client)
    cat = (await client.get("/api/v1/scales", headers=headers)).json()
    codes = {s["code"] for s in cat}
    assert "phq9" in codes and "gad7" in codes
    phq = next(s for s in cat if s["code"] == "phq9")
    assert len(phq["items"]) == 9 and len(phq["options"]) == 4 and phq["max_score"] == 27


async def test_request_answer_and_doctor_sees(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    # Médico solicita GAD-7.
    req = await client.post(f"/api/v1/patients/{patient['id']}/scales", headers=headers,
                            json={"scale_code": "gad7"})
    assert req.status_code == 201 and req.json()["status"] == "pending"

    # Paciente vê a pendente e responde.
    pend = (await client.get("/api/v1/patient/scales", headers=ph)).json()
    assert len(pend) == 1 and pend[0]["scale"]["code"] == "gad7"
    entry_id = pend[0]["id"]

    res = await client.post(f"/api/v1/patient/scales/{entry_id}", headers=ph,
                            json={"answers": [2, 2, 2, 2, 2, 1, 1]})
    assert res.status_code == 200
    assert res.json()["safety"] is None  # GAD-7 não sinaliza risco

    # Médico vê o resultado pontuado.
    done = (await client.get(f"/api/v1/patients/{patient['id']}/scales", headers=headers)).json()
    assert done[0]["status"] == "done" and done[0]["score"] == 12 and done[0]["severity"] == "Moderada"
    # Não aparece mais como pendente ao paciente.
    assert (await client.get("/api/v1/patient/scales", headers=ph)).json() == []


async def test_phq9_item9_triggers_alert(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    req = (await client.post(f"/api/v1/patients/{patient['id']}/scales", headers=headers,
                             json={"scale_code": "phq9"})).json()

    res = await client.post(f"/api/v1/patient/scales/{req['id']}", headers=ph,
                            json={"answers": [1, 1, 1, 1, 1, 1, 1, 1, 2]})  # item 9 = 2
    assert res.status_code == 200
    assert res.json()["safety"] is not None  # orientação de segurança ao paciente

    # Gerou um alerta imediato ao médico.
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert any(a["urgency"] == "immediate" and "PHQ-9" in a["reason"] for a in alerts)
    # A resposta ficou marcada como flagged (independente da faixa de gravidade
    # geral: score 10 = "Moderada", mas o item 9 sinaliza risco).
    done = (await client.get(f"/api/v1/patients/{patient['id']}/scales", headers=headers)).json()
    assert done[0]["flagged"] is True and done[0]["score"] == 10 and done[0]["severity"] == "Moderada"


async def test_invalid_answers_rejected(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    req = (await client.post(f"/api/v1/patients/{patient['id']}/scales", headers=headers,
                             json={"scale_code": "gad7"})).json()
    # Faltando respostas (GAD-7 tem 7 itens).
    r = await client.post(f"/api/v1/patient/scales/{req['id']}", headers=ph, json={"answers": [1, 2, 3]})
    assert r.status_code == 422


async def test_scales_isolation(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient(client, headers_a)
    req = (await client.post(f"/api/v1/patients/{patient['id']}/scales", headers=headers_a,
                             json={"scale_code": "gad7"})).json()
    headers_b = await _doctor(client, email="dr.b@x.com")
    assert (await client.get(f"/api/v1/patients/{patient['id']}/scales", headers=headers_b)).status_code == 404
    assert (await client.delete(f"/api/v1/scales/{req['id']}", headers=headers_b)).status_code == 404
