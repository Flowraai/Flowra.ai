"""Confirmação de consulta: envio ao agendar, botão manual, template e preferência."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client, headers, **over) -> dict:
    body = {"name": "João Silva", "contact": "+5543988580825", "consent_given": True}
    body.update(over)
    return (await client.post("/api/v1/patients", headers=headers, json=body)).json()


async def _appointment(client, headers, patient_id: str) -> dict:
    when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    return (await client.post(f"/api/v1/patients/{patient_id}/appointments", headers=headers,
                              json={"scheduled_at": when})).json()


async def test_confirmation_sent_on_create(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appointment(client, headers, patient["id"])
    # Padrão: confirma ao agendar.
    assert appt["confirmation_sent_at"] is not None


async def test_confirmation_skipped_when_pref_off(client: httpx.AsyncClient):
    headers = await _doctor(client)
    await client.patch("/api/v1/auth/me", headers=headers,
                       json={"message_prefs": {"send_appointment_confirmation": False}})
    patient = await _patient(client, headers)
    appt = await _appointment(client, headers, patient["id"])
    assert appt["confirmation_sent_at"] is None


async def test_manual_send_confirmation(client: httpx.AsyncClient):
    headers = await _doctor(client)
    await client.patch("/api/v1/auth/me", headers=headers,
                       json={"message_prefs": {"send_appointment_confirmation": False}})
    patient = await _patient(client, headers)
    appt = await _appointment(client, headers, patient["id"])
    assert appt["confirmation_sent_at"] is None

    r = await client.post(f"/api/v1/appointments/{appt['id']}/confirmation", headers=headers)
    assert r.status_code == 200
    assert r.json()["confirmation_sent_at"] is not None


async def test_manual_send_isolation(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appointment(client, headers, patient["id"])
    headers_b = await _doctor(client, email="dr.b@x.com")
    r = await client.post(f"/api/v1/appointments/{appt['id']}/confirmation", headers=headers_b)
    assert r.status_code == 404


def test_template_render_placeholders():
    from types import SimpleNamespace

    from app.models.enums import AppointmentKind
    from app.schemas.doctor import MessagePrefs
    from app.services.appointment_confirmation_service import DEFAULT_TEMPLATE, render_confirmation

    appt = SimpleNamespace(
        scheduled_at=datetime(2026, 5, 20, 14, 30, tzinfo=timezone.utc),
        kind=AppointmentKind.CONSULTATION,
        location="Sala 2",
    )
    patient = SimpleNamespace(name="Maria Souza")

    # Template customizado com placeholders.
    prefs = MessagePrefs(appointment_confirmation_template="Oi {paciente}, {tipo} dia {data} {hora}. {local}")
    _subj, body = render_confirmation(appt, patient, prefs)
    assert "Maria" in body and "consulta" in body
    assert "20/05/2026" in body and "Sala 2" in body

    # Sem template: usa o padrão do sistema.
    _subj, body = render_confirmation(appt, patient, MessagePrefs())
    assert body.startswith("Olá Maria")
    assert "{paciente}" not in DEFAULT_TEMPLATE or "{paciente}" not in body


def test_template_render_without_location():
    from types import SimpleNamespace

    from app.models.enums import AppointmentKind
    from app.schemas.doctor import MessagePrefs
    from app.services.appointment_confirmation_service import render_confirmation

    appt = SimpleNamespace(
        scheduled_at=datetime(2026, 5, 20, 14, 30, tzinfo=timezone.utc),
        kind=AppointmentKind.RETURN,
        location=None,
    )
    patient = SimpleNamespace(name="Ana")
    _subj, body = render_confirmation(appt, patient, MessagePrefs())
    # "retorno" aparece e não sobra placeholder nem espaço duplo do {local} vazio.
    assert "retorno" in body
    assert "  " not in body and "{local}" not in body
