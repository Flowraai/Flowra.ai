"""Testes do chat paciente↔médico (envio, leitura, notificação por push)."""

from __future__ import annotations

import httpx
import pytest


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str, str]] = []

    async def send(self, tokens: list[str], title: str, body: str) -> dict[str, str]:
        self.calls.append((list(tokens), title, body))
        return {t: "sent" for t in tokens}

    def tokens(self) -> set[str]:
        return {t for call, _, _ in self.calls for t in call}


@pytest.fixture
def recorder(monkeypatch) -> _Recorder:
    rec = _Recorder()
    monkeypatch.setattr("app.services.push_service.get_push_provider", lambda: rec)
    return rec


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers,
                              json={"name": "João", "consent_given": True})).json()


async def test_two_way_chat(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    await client.post(f"/api/v1/patients/{patient['id']}/messages", headers=headers,
                      json={"body": "Olá do médico"})
    await client.post("/api/v1/patient/messages", headers=ph, json={"body": "Olá do paciente"})

    doc_view = (await client.get(f"/api/v1/patients/{patient['id']}/messages",
                                 headers=headers)).json()
    pat_view = (await client.get("/api/v1/patient/messages", headers=ph)).json()
    assert len(doc_view) == 2 and len(pat_view) == 2
    assert {m["sender"] for m in doc_view} == {"doctor", "patient"}


async def test_reading_marks_other_party_messages_read(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    await client.post("/api/v1/patient/messages", headers=ph, json={"body": "Preciso de ajuda"})
    doc_view = (await client.get(f"/api/v1/patients/{patient['id']}/messages",
                                 headers=headers)).json()
    patient_msg = next(m for m in doc_view if m["sender"] == "patient")
    assert patient_msg["read_at"] is not None


async def test_message_pushes_to_recipient(client: httpx.AsyncClient, recorder: _Recorder):
    headers = await _doctor(client)
    await client.post("/api/v1/devices", headers=headers,
                      json={"token": "ExponentPushToken[med]", "platform": "android"})
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    await client.post("/api/v1/patient/devices", headers=ph,
                      json={"token": "ExponentPushToken[pac]", "platform": "ios"})

    await client.post(f"/api/v1/patients/{patient['id']}/messages", headers=headers,
                      json={"body": "Como está?"})
    await client.post("/api/v1/patient/messages", headers=ph, json={"body": "Melhor"})

    tokens = recorder.tokens()
    assert "ExponentPushToken[pac]" in tokens  # médico -> paciente
    assert "ExponentPushToken[med]" in tokens  # paciente -> médico


async def test_chat_isolation(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient(client, headers_a)
    headers_b = await _doctor(client, email="dr.b@x.com")
    r = await client.get(f"/api/v1/patients/{patient['id']}/messages", headers=headers_b)
    assert r.status_code == 404


async def test_manual_message_delivers_full_text(client: httpx.AsyncClient, monkeypatch):
    """Com deliver=True, o TEXTO da mensagem é entregue e o resultado é reportado."""
    delivered: list[str] = []

    async def _fake_deliver(session, patient, text):
        delivered.append(text)
        return "whatsapp"

    monkeypatch.setattr("app.api.routes.messages.deliver_whatsapp_status", _fake_deliver)

    headers = await _doctor(client)
    patient = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "consent_given": True, "contact": "+5543988580825"})).json()

    # Envio manual: entrega o texto e devolve delivery="whatsapp".
    r = await client.post(f"/api/v1/patients/{patient['id']}/messages", headers=headers,
                          json={"body": "Sua receita está pronta", "deliver": True})
    assert r.json()["delivery"] == "whatsapp"
    assert delivered == ["Sua receita está pronta"]

    # Envio comum: NÃO entrega o texto (fica no app, sem delivery).
    r2 = await client.post(f"/api/v1/patients/{patient['id']}/messages", headers=headers,
                           json={"body": "conteúdo interno"})
    assert r2.json()["delivery"] is None
    assert delivered == ["Sua receita está pronta"]


def test_normalize_msisdn_adds_brazil_ddi():
    from app.services.evolution import looks_deliverable, normalize_msisdn

    assert normalize_msisdn("43988580825") == "5543988580825"      # DDD+celular sem DDI
    assert normalize_msisdn("(43) 98858-0825") == "5543988580825"  # com máscara
    assert normalize_msisdn("+55 43 98858-0825") == "5543988580825"  # já com DDI
    assert normalize_msisdn("5543988580825") == "5543988580825"
    assert looks_deliverable("43988580825") is True
    assert looks_deliverable("98580825") is False  # sem DDD
