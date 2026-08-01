"""Verifica que os pontos de notificação disparam push aos donos com device."""

from __future__ import annotations

import httpx
import pytest

CRITICAL = {
    "mood": 1, "anxiety": 9, "slept_well": "nao", "sleep_hours": 2,
    "medication_taken": "nao", "crisis": "sim", "side_effects": "sim",
}


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


async def _doctor(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers,
                              json={"name": "João", "consent_given": True})).json()


async def test_prescription_issue_pushes_to_patient(client: httpx.AsyncClient, recorder: _Recorder):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    await client.post("/api/v1/patient/devices", headers=ph,
                      json={"token": "ExponentPushToken[pac]", "platform": "ios"})

    presc = (await client.post(f"/api/v1/patients/{patient['id']}/prescriptions", headers=headers,
                               json={"items": [{"name": "Sertralina", "dose": "50mg"}]})).json()
    await client.post(f"/api/v1/prescriptions/{presc['id']}/issue", headers=headers)

    assert "ExponentPushToken[pac]" in recorder.tokens()


async def test_alert_pushes_to_doctor(client: httpx.AsyncClient, recorder: _Recorder):
    headers = await _doctor(client)
    await client.post("/api/v1/devices", headers=headers,
                      json={"token": "ExponentPushToken[med]", "platform": "android"})
    patient = await _patient(client, headers)

    await client.post("/api/v1/patient/checkins",
                      headers={"X-Patient-Token": patient["access_token"]},
                      json={"structured_responses": CRITICAL})

    assert "ExponentPushToken[med]" in recorder.tokens()
