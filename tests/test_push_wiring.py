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


class _FailingProvider:
    """Simula um timeout/erro do provedor de push (ex.: Expo indisponível)."""

    async def send(self, tokens: list[str], title: str, body: str) -> dict[str, str]:
        raise RuntimeError("push provider timeout")


async def test_push_failure_does_not_drop_checkin_or_alert(
    client: httpx.AsyncClient, monkeypatch
):
    """CL-3: uma falha no push do alerta NÃO pode derrubar o check-in 🔴 nem o alerta.

    Antes da correção, o push rodava dentro da transação do check-in: um timeout da
    Expo fazia rollback e o check-in vermelho + o alerta sumiam sem o médico saber.
    """
    monkeypatch.setattr(
        "app.services.push_service.get_push_provider", lambda: _FailingProvider()
    )
    headers = await _doctor(client)
    await client.post("/api/v1/devices", headers=headers,
                      json={"token": "ExponentPushToken[med]", "platform": "android"})
    patient = await _patient(client, headers)

    # Check-in de alto risco, com o push do médico garantido a falhar.
    r = await client.post("/api/v1/patient/checkins",
                          headers={"X-Patient-Token": patient["access_token"]},
                          json={"structured_responses": CRITICAL})
    # O paciente recebe sucesso — a falha de notificação não vaza para ele.
    assert r.status_code == 201

    # O check-in foi persistido (o médico o vê no painel).
    checkins = (await client.get(
        f"/api/v1/patients/{patient['id']}/checkins", headers=headers)).json()
    assert len(checkins) == 1

    # E o alerta de alto risco continua lá para o médico revisar.
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert len(alerts) >= 1
    assert any(a["level"] in ("orange", "red") for a in alerts)
