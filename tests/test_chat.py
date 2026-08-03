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
