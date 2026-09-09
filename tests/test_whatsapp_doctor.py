"""WhatsApp por médico: conectar (QR)/status/desconectar + entrega pelo nº do médico."""

from __future__ import annotations

import uuid

import httpx

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services import evolution, notifications


async def _doctor(client: httpx.AsyncClient, email: str = "dr.wa@x.com") -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "senhaforte123", "name": "Dr. WA"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "evolution_api_url", "http://evo:8080")
    monkeypatch.setattr(settings, "evolution_api_key", "KEY")


async def test_status_requires_evolution_config(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "evolution_api_url", None)
    h = await _doctor(client)
    r = await client.get("/api/v1/whatsapp/status", headers=h)
    assert r.status_code == 503


async def test_connect_returns_qr_and_status(client: httpx.AsyncClient, monkeypatch):
    _configure(monkeypatch)

    async def fake_ensure(name):
        return None

    async def fake_connect(name):
        return {"state": "connecting", "qr": "data:image/png;base64,AAA", "pairing_code": None}

    calls = {"state": "open"}

    async def fake_state(name):
        return calls["state"]

    monkeypatch.setattr(evolution, "ensure_instance", fake_ensure)
    monkeypatch.setattr(evolution, "connect", fake_connect)
    monkeypatch.setattr(evolution, "state", fake_state)

    h = await _doctor(client)
    # antes de conectar: desconectado
    r = await client.get("/api/v1/whatsapp/status", headers=h)
    assert r.status_code == 200 and r.json()["connected"] is False

    # conectar -> devolve QR e grava a instância
    r = await client.post("/api/v1/whatsapp/connect", headers=h)
    assert r.status_code == 200 and r.json()["qr"].startswith("data:image")

    # status agora consulta a Evolution (mock "open") -> conectado
    r = await client.get("/api/v1/whatsapp/status", headers=h)
    assert r.json()["connected"] is True and r.json()["state"] == "open"

    # desconectar -> limpa
    r = await client.post("/api/v1/whatsapp/disconnect", headers=h)
    assert r.json()["connected"] is False


async def test_deliver_uses_doctor_whatsapp(client: httpx.AsyncClient, monkeypatch):
    _configure(monkeypatch)
    sent = {}

    async def fake_send_text(instance, number, text):
        sent["instance"] = instance
        sent["number"] = number
        sent["text"] = text

    monkeypatch.setattr(evolution, "send_text", fake_send_text)

    h = await _doctor(client)
    p = (await client.post(
        "/api/v1/patients", headers=h,
        json={"name": "Ana", "contact": "+5541999998888", "consent_given": True},
    )).json()

    # conecta o WhatsApp do médico (grava a instância)
    async def fake_ensure(name):
        return None

    async def fake_connect(name):
        return {"state": "connecting", "qr": "data:image/png;base64,AAA"}

    monkeypatch.setattr(evolution, "ensure_instance", fake_ensure)
    monkeypatch.setattr(evolution, "connect", fake_connect)
    await client.post("/api/v1/whatsapp/connect", headers=h)

    # entrega ao paciente deve sair pela instância do médico
    async with AsyncSessionLocal() as s:
        from app.models.patient import Patient
        patient = await s.get(Patient, uuid.UUID(p["id"]))
        ok = await notifications.deliver_to_patient(s, patient, "Assunto", "Corpo")
        assert ok is True

    assert sent["number"] == "+5541999998888"
    assert sent["instance"].startswith("care_")
    assert "Assunto" in sent["text"] and "Corpo" in sent["text"]


async def test_deliver_falls_back_without_instance(client: httpx.AsyncClient, monkeypatch):
    _configure(monkeypatch)
    fell_back = {}

    async def fake_send_plain(target, subject, body):
        fell_back["target"] = target

    monkeypatch.setattr(notifications, "send_plain", fake_send_plain)

    h = await _doctor(client, email="dr.wa2@x.com")
    p = (await client.post(
        "/api/v1/patients", headers=h,
        json={"name": "Bia", "contact": "+5541988887777", "consent_given": True},
    )).json()

    async with AsyncSessionLocal() as s:
        from app.models.patient import Patient
        patient = await s.get(Patient, uuid.UUID(p["id"]))
        # médico sem WhatsApp conectado -> cai no fallback (send_plain)
        await notifications.deliver_to_patient(s, patient, "Assunto", "Corpo")

    assert fell_back["target"] == "+5541988887777"
