"""Lembrete diário de check-in: envio, dedupe, quem já fez, e preferência."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.patient import Patient
from app.services.checkin_reminder_service import scan_checkin_reminders


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5543988580825", "consent_given": True})).json()


async def _scan() -> dict:
    async with AsyncSessionLocal() as s:
        res = await scan_checkin_reminders(s)
        await s.commit()
    return res


async def _set(patient_id: str, **fields) -> None:
    async with AsyncSessionLocal() as s:
        p = await s.scalar(select(Patient).where(Patient.id == patient_id))
        for k, v in fields.items():
            setattr(p, k, v)
        await s.commit()


async def test_reminder_sent_to_patient_without_checkin_today(client: httpx.AsyncClient):
    settings.checkin_reminder_hour_utc = 0  # sempre dentro da janela
    headers = await _doctor(client)
    patient = await _patient(client, headers)  # sem check-in → deve lembrar

    res = await _scan()
    assert res["reminders"] == 1

    # Marcou o envio (dedupe).
    async with AsyncSessionLocal() as s:
        p = await s.scalar(select(Patient).where(Patient.id == patient["id"]))
        assert p.checkin_reminder_sent_at is not None

    # Rodar de novo no mesmo dia não reenvia.
    assert (await _scan())["reminders"] == 0


async def test_no_reminder_if_checked_in_today(client: httpx.AsyncClient):
    settings.checkin_reminder_hour_utc = 0
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    await _set(patient["id"], last_checkin_at=datetime.now(timezone.utc))
    assert (await _scan())["reminders"] == 0


async def test_reminder_again_next_day(client: httpx.AsyncClient):
    settings.checkin_reminder_hour_utc = 0
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    # Lembrete "de ontem" e check-in "de ontem" → hoje deve lembrar de novo.
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    await _set(patient["id"], checkin_reminder_sent_at=yesterday, last_checkin_at=yesterday)
    assert (await _scan())["reminders"] == 1


async def test_respects_doctor_pref_off(client: httpx.AsyncClient):
    settings.checkin_reminder_hour_utc = 0
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    await client.patch("/api/v1/auth/me", headers=headers,
                       json={"message_prefs": {"send_checkin_reminder": False}})
    res = await _scan()
    assert res["reminders"] == 0 and res["skipped_by_pref"] == 1
    # Ainda marca o envio para não reprocessar.
    async with AsyncSessionLocal() as s:
        p = await s.scalar(select(Patient).where(Patient.id == patient["id"]))
        assert p.checkin_reminder_sent_at is not None


async def test_too_early_sends_nothing(client: httpx.AsyncClient):
    settings.checkin_reminder_hour_utc = 24  # nunca alcançado (hora vai de 0 a 23)
    await _doctor(client)  # garante ao menos um paciente possível
    res = await _scan()
    assert res.get("too_early") is True and res["reminders"] == 0
    settings.checkin_reminder_hour_utc = 21  # restaura o padrão
