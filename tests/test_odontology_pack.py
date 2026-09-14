"""Vertical de Odontologia: prova a plugabilidade fora de saúde mental."""

from __future__ import annotations

import httpx


async def _dentist(client: httpx.AsyncClient, email: str = "dr.dente@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dr. Dente"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    await client.patch("/api/v1/auth/me", headers=headers, json={"specialty": "odontologia"})
    return headers


async def _patient(client, headers, contact="+5543988580830") -> dict:
    p = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "Paciente", "contact": contact, "consent_given": True})).json()
    return {"X-Patient-Token": p["access_token"]}


async def test_care_features_and_specialty(client: httpx.AsyncClient):
    headers = await _dentist(client)
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["care"]["specialty"] == "odontologia" and me["care"]["label"] == "Odontologia"
    assert me["care"]["features"]["medicacao"] is True   # dentista prescreve
    assert me["care"]["features"]["wearables"] is False
    opts = (await client.get("/api/v1/auth/care/specialties", headers=headers)).json()
    assert "odontologia" in {o["key"] for o in opts}


async def test_protocol_is_dental_not_mental_health(client: httpx.AsyncClient):
    headers = await _dentist(client)
    ph = await _patient(client, headers)
    proto = (await client.get("/api/v1/patient/protocol", headers=ph)).json()
    codes = {q["code"] for q in proto["questions"]}
    assert "pain" in codes and "bleeding" in codes and "fever" in codes
    assert "mood" not in codes and "self_harm" not in codes


async def test_no_scales_catalog(client: httpx.AsyncClient):
    headers = await _dentist(client)
    assert (await client.get("/api/v1/scales", headers=headers)).json() == []


async def test_high_pain_triggers_immediate_alert(client: httpx.AsyncClient):
    headers = await _dentist(client)
    ph = await _patient(client, headers, "+5543988580831")
    resp = {"pain": 9, "bleeding": "nao", "swelling": "nenhum", "fever": "nao",
            "medication_taken": "sim"}
    r = await client.post("/api/v1/patient/checkins", headers=ph, json={"structured_responses": resp})
    assert r.status_code in (200, 201)
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert any(a["urgency"] == "immediate" and "dor" in a["reason"].lower() for a in alerts)


async def test_bleeding_triggers_alert(client: httpx.AsyncClient):
    headers = await _dentist(client)
    ph = await _patient(client, headers, "+5543988580832")
    resp = {"pain": 1, "bleeding": "sim", "swelling": "nenhum", "fever": "nao",
            "medication_taken": "sim"}
    await client.post("/api/v1/patient/checkins", headers=ph, json={"structured_responses": resp})
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert any("sangramento" in a["reason"].lower() for a in alerts)


async def test_free_text_crisis_not_analyzed_in_dentistry(client: httpx.AsyncClient):
    # Em odontologia o analisador de saúde mental é desligado: um texto que
    # dispararia risco em psiquiatria NÃO deve gerar alerta aqui.
    headers = await _dentist(client)
    ph = await _patient(client, headers, "+5543988580833")
    resp = {"pain": 0, "bleeding": "nao", "swelling": "nenhum", "fever": "nao",
            "medication_taken": "sim"}
    await client.post("/api/v1/patient/checkins", headers=ph,
                      json={"structured_responses": resp, "free_text": "essa dor está me matando"})
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert alerts == []  # check-in verde, sem alerta


async def test_cannot_delete_dental_protected_question(client: httpx.AsyncClient):
    # A pergunta de dor é protegida no pacote de odontologia (o risco depende dela).
    headers = await _dentist(client)
    survey = (await client.get("/api/v1/survey", headers=headers)).json()
    pain_q = next(q for q in survey["questions"] if q["code"] == "pain")
    assert pain_q["protected"] is True
    r = await client.delete(f"/api/v1/survey/questions/{pain_q['id']}", headers=headers)
    assert r.status_code == 400
