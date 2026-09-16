"""Confirmação de mão dupla: webhook da Evolution → consulta confirmada/remarcar."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.doctor import Doctor
from app.models.user import User

TOKEN = "webhook-tok-test"


@pytest.fixture
def _enable_webhook(monkeypatch):
    monkeypatch.setattr(settings, "evolution_webhook_token", TOKEN)
    yield


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _set_instance(email: str, instance: str) -> None:
    async with AsyncSessionLocal() as s:
        user = (await s.execute(select(User).where(User.email == email))).scalar_one()
        doctor = (
            await s.execute(select(Doctor).where(Doctor.user_id == user.id))
        ).scalar_one()
        doctor.whatsapp_instance = instance
        await s.commit()


async def _patient(client, headers, **over) -> dict:
    body = {"name": "João Silva", "contact": "+5543988580825", "consent_given": True}
    body.update(over)
    return (await client.post("/api/v1/patients", headers=headers, json=body)).json()


async def _appointment(client, headers, patient_id: str) -> dict:
    when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    return (await client.post(f"/api/v1/patients/{patient_id}/appointments", headers=headers,
                              json={"scheduled_at": when})).json()


def _payload(instance: str, number: str, text: str) -> dict:
    return {
        "event": "messages.upsert",
        "instance": instance,
        "data": {
            "key": {"remoteJid": f"{number}@s.whatsapp.net", "fromMe": False, "id": "x"},
            "message": {"conversation": text},
            "pushName": "João",
        },
    }


async def test_webhook_disabled_without_token(client: httpx.AsyncClient):
    # Sem EVOLUTION_WEBHOOK_TOKEN configurado, o endpoint não existe (404).
    r = await client.post("/api/v1/webhooks/evolution/qualquer", json={})
    assert r.status_code == 404


async def test_webhook_wrong_token(client: httpx.AsyncClient, _enable_webhook):
    r = await client.post("/api/v1/webhooks/evolution/errado", json={})
    assert r.status_code == 404


async def test_confirm_via_whatsapp(client: httpx.AsyncClient, _enable_webhook):
    headers = await _doctor(client)
    await _set_instance("dra.ana@clinica.com", "care_test")
    patient = await _patient(client, headers)
    appt = await _appointment(client, headers, patient["id"])
    assert appt["status"] == "scheduled"

    r = await client.post(
        f"/api/v1/webhooks/evolution/{TOKEN}",
        json=_payload("care_test", "5543988580825", "Sim"),
    )
    assert r.status_code == 200 and r.json()["status"] == "confirmed"

    appts = (await client.get("/api/v1/appointments/upcoming", headers=headers)).json()
    assert appts[0]["status"] == "confirmed"


async def test_reschedule_via_whatsapp(client: httpx.AsyncClient, _enable_webhook):
    headers = await _doctor(client)
    await _set_instance("dra.ana@clinica.com", "care_test")
    patient = await _patient(client, headers)
    await _appointment(client, headers, patient["id"])

    r = await client.post(
        f"/api/v1/webhooks/evolution/{TOKEN}",
        json=_payload("care_test", "5543988580825", "Preciso remarcar"),
    )
    assert r.status_code == 200 and r.json()["status"] == "reschedule_requested"

    appts = (await client.get("/api/v1/appointments/upcoming", headers=headers)).json()
    assert appts[0]["reschedule_requested_at"] is not None


async def test_unknown_number_is_ignored(client: httpx.AsyncClient, _enable_webhook):
    headers = await _doctor(client)
    await _set_instance("dra.ana@clinica.com", "care_test")
    patient = await _patient(client, headers)
    await _appointment(client, headers, patient["id"])

    r = await client.post(
        f"/api/v1/webhooks/evolution/{TOKEN}",
        json=_payload("care_test", "5511999990000", "Sim"),  # número que não é do paciente
    )
    assert r.status_code == 200 and r.json()["status"] == "ignored"


async def test_unrecognized_text_is_ignored(client: httpx.AsyncClient, _enable_webhook):
    headers = await _doctor(client)
    await _set_instance("dra.ana@clinica.com", "care_test")
    patient = await _patient(client, headers)
    await _appointment(client, headers, patient["id"])

    r = await client.post(
        f"/api/v1/webhooks/evolution/{TOKEN}",
        json=_payload("care_test", "5543988580825", "bom dia, tudo bem?"),
    )
    assert r.json()["status"] == "ignored"


def test_parse_and_interpret_unit():
    from app.services.whatsapp_inbound_service import interpret, parse_event

    # extendedTextMessage + fromMe ignorado + grupo ignorado
    assert parse_event({"instance": "i", "data": {"key": {"remoteJid": "555@s.whatsapp.net"},
                        "message": {"extendedTextMessage": {"text": "sim"}}}}).text == "sim"
    assert parse_event({"instance": "i", "data": {"key": {"remoteJid": "5@s.whatsapp.net",
                        "fromMe": True}, "message": {"conversation": "sim"}}}) is None
    assert parse_event({"instance": "i", "data": {"key": {"remoteJid": "5@g.us"},
                        "message": {"conversation": "sim"}}}) is None

    assert interpret("Sim") == "confirm"
    assert interpret("CONFIRMO!") == "confirm"
    assert interpret("👍") == "confirm"
    assert interpret("remarcar") == "reschedule"
    assert interpret("não") == "reschedule"
    assert interpret("bom dia") is None
