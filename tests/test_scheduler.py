"""Agendador: as varreduras periódicas rodam e produzem os efeitos esperados."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import update

from app.db.session import AsyncSessionLocal
from app.models.patient import Patient
from app.scripts.scheduler import run_once


async def _doctor(client: httpx.AsyncClient, email: str = "dr.sched@x.com") -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "senhaforte123", "name": "Dr. Sched"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_run_once_smoke_empty(client: httpx.AsyncClient):
    # Sem pacientes, o ciclo roda sem erro.
    await run_once()


async def test_scheduler_creates_inactivity_alert(client: httpx.AsyncClient):
    h = await _doctor(client)
    p = await client.post(
        "/api/v1/patients", headers=h,
        json={"name": "Ana", "contact": "+5511999999999", "consent_given": True},
    )
    pid = uuid.UUID(p.json()["id"])

    # Sem alerta de inatividade ainda.
    before = (await client.get("/api/v1/alerts", headers=h)).json()
    assert not any(a["checkin_id"] is None for a in before)

    # "Envelhece" o paciente para ficar inativo (sem check-in há dias).
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(Patient)
            .where(Patient.id == pid)
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=5))
        )
        await s.commit()

    await run_once()

    alerts = (await client.get("/api/v1/alerts", headers=h)).json()
    assert any(a["checkin_id"] is None and "sem check-in" in a["reason"] for a in alerts)
