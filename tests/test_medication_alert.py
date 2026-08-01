"""Testes do alerta ao médico por faltas consecutivas de medicação."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.db.session import AsyncSessionLocal
from app.models.enums import MedicationIntakeStatus
from app.models.medication import MedicationIntake, MedicationPlan
from app.services.medication_service import maybe_alert_missed_streak


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def _setup(client: httpx.AsyncClient, times=("08:00",)) -> dict:
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


async def _insert(ctx: dict, days_ago: int, status: MedicationIntakeStatus) -> None:
    async with AsyncSessionLocal() as s:
        s.add(MedicationIntake(
            tenant_id=uuid.UUID(ctx["tenant_id"]),
            plan_id=uuid.UUID(ctx["plan"]["id"]),
            patient_id=uuid.UUID(ctx["patient"]["id"]),
            scheduled_for=datetime.now(timezone.utc) - timedelta(days=days_ago),
            status=status,
        ))
        await s.commit()


async def _run_check(ctx: dict):
    async with AsyncSessionLocal() as s:
        plan = await s.get(MedicationPlan, uuid.UUID(ctx["plan"]["id"]))
        result = await maybe_alert_missed_streak(s, plan)
        await s.commit()
        return result


async def _alert_count(client: httpx.AsyncClient, headers: dict) -> int:
    return len((await client.get("/api/v1/alerts", headers=headers)).json())


async def test_alert_on_three_consecutive_missed(client: httpx.AsyncClient):
    ctx = await _setup(client)
    for d in (3, 4, 5):
        await _insert(ctx, d, MedicationIntakeStatus.MISSED)

    alert = await _run_check(ctx)
    assert alert is not None
    alerts = (await client.get("/api/v1/alerts", headers=ctx["headers"])).json()
    assert len(alerts) == 1
    assert "vezes seguidas" in alerts[0]["reason"]
    assert alerts[0]["urgency"] == "routine"


async def test_no_duplicate_alert_while_open(client: httpx.AsyncClient):
    ctx = await _setup(client)
    for d in (3, 4, 5):
        await _insert(ctx, d, MedicationIntakeStatus.MISSED)

    assert await _run_check(ctx) is not None
    # segunda checagem não duplica (alerta em aberto para o plano)
    assert await _run_check(ctx) is None
    assert await _alert_count(client, ctx["headers"]) == 1


async def test_streak_broken_by_taken(client: httpx.AsyncClient):
    ctx = await _setup(client)
    await _insert(ctx, 3, MedicationIntakeStatus.MISSED)
    await _insert(ctx, 4, MedicationIntakeStatus.TAKEN)  # quebra a sequência
    await _insert(ctx, 5, MedicationIntakeStatus.MISSED)

    assert await _run_check(ctx) is None
    assert await _alert_count(client, ctx["headers"]) == 0


async def test_respond_missed_can_trigger_alert(client: httpx.AsyncClient):
    ctx = await _setup(client, times=("00:00",))  # gera dose hoje
    await _insert(ctx, 1, MedicationIntakeStatus.MISSED)
    await _insert(ctx, 2, MedicationIntakeStatus.MISSED)

    ph = {"X-Patient-Token": ctx["patient"]["access_token"]}
    intake_id = (await client.get("/api/v1/patient/medications/today", headers=ph)).json()[0]["intake_id"]
    r = await client.post(f"/api/v1/patient/medications/intakes/{intake_id}/respond",
                          headers=ph, json={"status": "missed"})
    assert r.status_code == 200

    assert await _alert_count(client, ctx["headers"]) == 1
