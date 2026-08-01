"""Testes do agendador de medicação (scan: lembretes + marcar 'não tomou')."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.db.session import AsyncSessionLocal
from app.models.enums import MedicationIntakeStatus
from app.models.medication import MedicationIntake
from app.services.medication_service import scan_due_medications


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def _setup(client: httpx.AsyncClient, times=("00:00",)) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    tenant_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["tenant_id"]
    patient = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5511999999999", "consent_given": True})).json()
    plan = (await client.post(f"/api/v1/patients/{patient['id']}/medications", headers=headers,
                              json={"name": "Sertralina", "dose": "50mg",
                                    "times": list(times), "start_date": _today()})).json()
    return {"headers": headers, "tenant_id": tenant_id, "patient": patient, "plan": plan}


async def _scan() -> dict:
    async with AsyncSessionLocal() as session:
        result = await scan_due_medications(session)
        await session.commit()
    return result


async def test_scan_creates_due_intake_and_reminds(client: httpx.AsyncClient):
    ctx = await _setup(client, times=("00:00",))  # 00:00 já venceu hoje

    result = await _scan()
    assert result["reminders"] >= 1

    # a dose aparece para o paciente
    doses = (await client.get("/api/v1/patient/medications/today",
             headers={"X-Patient-Token": ctx["patient"]["access_token"]})).json()
    assert len(doses) == 1

    # segundo scan não reenvia (idempotente via reminded_at)
    again = await _scan()
    assert again["reminders"] == 0


async def test_scan_marks_previous_day_pending_as_missed(client: httpx.AsyncClient):
    ctx = await _setup(client, times=("08:00",))
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)

    async with AsyncSessionLocal() as session:
        session.add(MedicationIntake(
            tenant_id=uuid.UUID(ctx["tenant_id"]),
            plan_id=uuid.UUID(ctx["plan"]["id"]),
            patient_id=uuid.UUID(ctx["patient"]["id"]),
            scheduled_for=yesterday,
            status=MedicationIntakeStatus.PENDING,
        ))
        await session.commit()

    result = await _scan()
    assert result["marked_missed"] >= 1

    adherence = (await client.get(
        f"/api/v1/patients/{ctx['patient']['id']}/medications/adherence",
        headers=ctx["headers"])).json()
    assert adherence["missed"] >= 1


async def test_scan_script_runs(client: httpx.AsyncClient):
    # o setup garante schema/dados; o scan não deve levantar
    await _setup(client)
    result = await _scan()
    assert "reminders" in result and "marked_missed" in result
