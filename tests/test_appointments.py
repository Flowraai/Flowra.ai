"""Testes de consultas/retornos (agenda)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx


def _in(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers,
                              json={"name": "João", "consent_given": True})).json()


async def _appt(client: httpx.AsyncClient, headers: dict, patient_id: str, when: str) -> dict:
    return (await client.post(f"/api/v1/patients/{patient_id}/appointments", headers=headers,
                              json={"scheduled_at": when, "kind": "consultation"})).json()


async def test_create_and_list(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appt(client, headers, patient["id"], _in(2))
    assert appt["status"] == "scheduled"

    lst = (await client.get(f"/api/v1/patients/{patient['id']}/appointments",
                            headers=headers)).json()
    assert len(lst) == 1


async def test_upcoming_excludes_past_and_cancelled(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    future = await _appt(client, headers, patient["id"], _in(1))
    await _appt(client, headers, patient["id"], _in(-1))  # passada
    cancel = await _appt(client, headers, patient["id"], _in(3))
    await client.patch(f"/api/v1/appointments/{cancel['id']}", headers=headers,
                       json={"status": "cancelled"})

    upcoming = (await client.get("/api/v1/appointments/upcoming", headers=headers)).json()
    ids = {a["id"] for a in upcoming}
    assert future["id"] in ids
    assert cancel["id"] not in ids
    assert len(upcoming) == 1


async def test_range_returns_all_statuses_in_window(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    inside = await _appt(client, headers, patient["id"], _in(2))
    past = await _appt(client, headers, patient["id"], _in(-2))  # dentro da janela, no passado
    await _appt(client, headers, patient["id"], _in(40))         # fora da janela
    await client.patch(f"/api/v1/appointments/{past['id']}", headers=headers,
                       json={"status": "completed"})

    start = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    res = (await client.get("/api/v1/appointments/range", headers=headers,
                            params={"start": start, "end": end})).json()
    ids = {a["id"] for a in res}
    assert inside["id"] in ids and past["id"] in ids  # inclui concluída (passada)
    assert len(res) == 2  # a de +40 dias ficou de fora


async def test_patient_sees_and_confirms(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appt(client, headers, patient["id"], _in(2))
    ph = {"X-Patient-Token": patient["access_token"]}

    mine = (await client.get("/api/v1/patient/appointments", headers=ph)).json()
    assert len(mine) == 1

    r = await client.post(f"/api/v1/patient/appointments/{appt['id']}/confirm", headers=ph)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"


async def test_cannot_confirm_cancelled(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appt(client, headers, patient["id"], _in(2))
    await client.patch(f"/api/v1/appointments/{appt['id']}", headers=headers,
                       json={"status": "cancelled"})
    ph = {"X-Patient-Token": patient["access_token"]}
    r = await client.post(f"/api/v1/patient/appointments/{appt['id']}/confirm", headers=ph)
    assert r.status_code == 409


async def test_appointment_isolation(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient(client, headers_a)
    appt = await _appt(client, headers_a, patient["id"], _in(2))
    headers_b = await _doctor(client, email="dr.b@x.com")

    r = await client.patch(f"/api/v1/appointments/{appt['id']}", headers=headers_b,
                           json={"status": "completed"})
    assert r.status_code == 404


async def test_patient_requests_reschedule(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appt(client, headers, patient["id"], _in(2))
    ph = {"X-Patient-Token": patient["access_token"]}

    r = await client.post(
        f"/api/v1/patient/appointments/{appt['id']}/reschedule",
        headers=ph, json={"note": "só à tarde"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["reschedule_requested_at"] is not None
    assert data["reschedule_note"] == "só à tarde"

    # O médico vê o pedido na consulta.
    lst = (await client.get(f"/api/v1/patients/{patient['id']}/appointments",
                            headers=headers)).json()
    assert lst[0]["reschedule_requested_at"] is not None


async def test_doctor_reschedule_clears_request_and_resets_reminder(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appt(client, headers, patient["id"], _in(2))
    ph = {"X-Patient-Token": patient["access_token"]}
    await client.post(f"/api/v1/patient/appointments/{appt['id']}/reschedule",
                      headers=ph, json={"note": "manhã, por favor"})

    # Médico propõe um novo horário → limpa o pedido e volta para "agendada".
    updated = (await client.patch(f"/api/v1/appointments/{appt['id']}", headers=headers,
                                  json={"scheduled_at": _in(5)})).json()
    assert updated["reschedule_requested_at"] is None
    assert updated["reschedule_note"] is None
    assert updated["status"] == "scheduled"


async def test_confirm_clears_reschedule_request(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appt(client, headers, patient["id"], _in(2))
    ph = {"X-Patient-Token": patient["access_token"]}
    await client.post(f"/api/v1/patient/appointments/{appt['id']}/reschedule",
                      headers=ph, json={})
    confirmed = (await client.post(
        f"/api/v1/patient/appointments/{appt['id']}/confirm", headers=ph)).json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["reschedule_requested_at"] is None
