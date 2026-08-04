"""Testes do chat paciente↔IA (resposta, thread separada, alerta em risco)."""

from __future__ import annotations

import httpx


async def _doctor(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers,
                              json={"name": "João", "consent_given": True})).json()


async def test_ai_chat_replies_and_persists(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    r = await client.post("/api/v1/patient/ai-chat", headers=ph,
                          json={"body": "Oi, tudo bem?"})
    assert r.status_code == 201
    assert r.json()["sender"] == "ai" and r.json()["body"]

    history = (await client.get("/api/v1/patient/ai-chat", headers=ph)).json()
    assert len(history) == 2  # mensagem do paciente + resposta da IA
    assert {m["sender"] for m in history} == {"patient", "ai"}


async def test_ai_chat_is_separate_from_care_thread(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    await client.post("/api/v1/patient/messages", headers=ph, json={"body": "msg pro médico"})
    await client.post("/api/v1/patient/ai-chat", headers=ph, json={"body": "msg pra IA"})

    care = (await client.get("/api/v1/patient/messages", headers=ph)).json()
    ai = (await client.get("/api/v1/patient/ai-chat", headers=ph)).json()
    assert len(care) == 1 and care[0]["body"] == "msg pro médico"
    # a mensagem enviada ao médico não vaza para a thread da IA (e vice-versa)
    assert all(m["body"] != "msg pro médico" for m in ai)
    assert any(m["body"] == "msg pra IA" for m in ai)
    # a thread de cuidado do médico não inclui as mensagens da IA
    doc_view = (await client.get(f"/api/v1/patients/{patient['id']}/messages",
                                 headers=headers)).json()
    assert len(doc_view) == 1


async def test_ai_chat_llm_reply(client: httpx.AsyncClient, monkeypatch):
    async def _fake(system: str, user: str, temperature: float = 0.2) -> str:
        return "Que bom te ver por aqui! Como posso ajudar?"

    monkeypatch.setattr("app.services.ai_chat_service.chat_complete", _fake)
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    r = await client.post("/api/v1/patient/ai-chat", headers=ph, json={"body": "olá"})
    assert r.json()["body"] == "Que bom te ver por aqui! Como posso ajudar?"


async def test_ai_chat_crisis_alerts_doctor(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    r = await client.post("/api/v1/patient/ai-chat", headers=ph,
                          json={"body": "não quero mais viver"})
    assert r.status_code == 201
    assert "188" in r.json()["body"]  # mensagem de segurança (CVV)

    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert len(alerts) == 1
    assert alerts[0]["level"] == "red" and alerts[0]["urgency"] == "immediate"
