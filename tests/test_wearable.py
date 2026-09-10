"""Dispositivos vestíveis: conexão (demo), sincronização e leitura pelo médico."""

from __future__ import annotations

import httpx


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5543988580825", "consent_given": True})).json()


async def test_connect_and_read(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    # Antes de conectar.
    before = (await client.get("/api/v1/patient/wearable", headers=ph)).json()
    assert before["connected"] is False and before["latest"] is None

    # Conecta (demo é instantâneo → sem OAuth, já sincroniza).
    c = await client.post("/api/v1/patient/wearable/connect", headers=ph)
    assert c.status_code == 200
    assert c.json()["connected"] is True and c.json()["connect_url"] is None

    after = (await client.get("/api/v1/patient/wearable", headers=ph)).json()
    assert after["connected"] is True
    assert after["latest"] is not None
    assert after["latest"]["sleep_minutes"] is not None
    assert after["avg_resting_hr"] is not None
    assert len(after["days"]) >= 1


async def test_doctor_sees_wearable(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    await client.post("/api/v1/patient/wearable/connect", headers=ph)

    r = await client.get(f"/api/v1/patients/{patient['id']}/wearable", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["connected"] is True and data["latest"]["steps"] is not None


async def test_sync_requires_connection(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    # Sem conexão → 409.
    assert (await client.post("/api/v1/patient/wearable/sync", headers=ph)).status_code == 409


async def test_disconnect(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    await client.post("/api/v1/patient/wearable/connect", headers=ph)
    assert (await client.post("/api/v1/patient/wearable/disconnect", headers=ph)).status_code == 204
    after = (await client.get("/api/v1/patient/wearable", headers=ph)).json()
    assert after["connected"] is False


async def test_mobile_push_samples(client: httpx.AsyncClient):
    """App de celular envia os dias lidos do HealthKit/Health Connect (upsert)."""
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    r = await client.post("/api/v1/patient/wearable/samples", headers=ph, json={
        "source": "health_connect",
        "days": [
            {"day": "2026-09-09", "sleep_minutes": 445, "resting_hr": 60, "hrv_ms": 42, "steps": 9100},
            {"day": "2026-09-10", "sleep_minutes": 410, "steps": 5200},
        ],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["connected"] is True
    assert data["latest"]["day"] == "2026-09-10" and data["latest"]["sleep_minutes"] == 410

    # Reenvio do mesmo dia atualiza (não duplica) e não zera métricas ausentes.
    r2 = await client.post("/api/v1/patient/wearable/samples", headers=ph, json={
        "source": "health_connect",
        "days": [{"day": "2026-09-10", "resting_hr": 58}],
    })
    latest = r2.json()["latest"]
    assert latest["resting_hr"] == 58 and latest["sleep_minutes"] == 410  # sono preservado

    # O médico vê os mesmos dados.
    doc = (await client.get(f"/api/v1/patients/{patient['id']}/wearable", headers=headers)).json()
    assert doc["connected"] is True and doc["latest"]["steps"] == 5200


async def test_mobile_push_rejects_bad_values(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    r = await client.post("/api/v1/patient/wearable/samples", headers=ph, json={
        "days": [{"day": "2026-09-10", "resting_hr": 999}],  # fora do intervalo
    })
    assert r.status_code == 422


async def test_wearable_in_doctor_summary(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    await client.post("/api/v1/patient/wearable/connect", headers=ph)

    summary = (await client.get(f"/api/v1/patients/{patient['id']}/summary", headers=headers)).json()
    assert summary["context"]["wearable"] is not None
    assert summary["context"]["wearable"]["avg_sleep_minutes"] is not None
