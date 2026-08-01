"""Testes do agendador de lembretes de consulta."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.db.session import AsyncSessionLocal
from app.services.appointment_service import scan_appointment_reminders


def _in_hours(h: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=h)).isoformat()


async def _setup(client: httpx.AsyncClient, when: str, contact: str | None = "+5511999999999") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    body = {"name": "João", "consent_given": True}
    if contact:
        body["contact"] = contact
    patient = (await client.post("/api/v1/patients", headers=headers, json=body)).json()
    appt = (await client.post(f"/api/v1/patients/{patient['id']}/appointments", headers=headers,
                              json={"scheduled_at": when, "kind": "consultation"})).json()
    return {"headers": headers, "patient": patient, "appt": appt}


async def _scan() -> dict:
    async with AsyncSessionLocal() as session:
        result = await scan_appointment_reminders(session)
        await session.commit()
    return result


async def test_reminds_upcoming_appointment(client: httpx.AsyncClient):
    await _setup(client, _in_hours(2))  # dentro da janela de 24h
    result = await _scan()
    assert result["reminders"] >= 1
    # idempotente: segundo scan não reenvia
    assert (await _scan())["reminders"] == 0


async def test_does_not_remind_far_appointment(client: httpx.AsyncClient):
    await _setup(client, _in_hours(48))  # além da janela de 24h
    assert (await _scan())["reminders"] == 0


async def test_does_not_remind_cancelled(client: httpx.AsyncClient):
    ctx = await _setup(client, _in_hours(2))
    await client.patch(f"/api/v1/appointments/{ctx['appt']['id']}", headers=ctx["headers"],
                       json={"status": "cancelled"})
    assert (await _scan())["reminders"] == 0
