"""Testes do serviço/canal de notificações."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.enums import NotificationChannel, NotificationStatus
from app.models.notification import Notification
from app.services.notification_channels import (
    EmailChannel,
    LogChannel,
    WebhookChannel,
    get_active_channels,
)

CRITICAL = {
    "mood": 1, "anxiety": 9, "slept_well": "nao", "sleep_hours": 2,
    "medication_taken": "nao", "crisis": "sim", "side_effects": "sim",
}


# ---------- Unitários (sem banco) ----------
def test_default_channel_is_log():
    channels = get_active_channels()
    assert [type(c) for c in channels] == [LogChannel]


def test_unknown_channel_falls_back_to_log(monkeypatch):
    monkeypatch.setattr(settings, "notification_channels", ["inexistente"])
    channels = get_active_channels()
    assert len(channels) == 1 and isinstance(channels[0], LogChannel)


def test_configured_channels_resolve(monkeypatch):
    monkeypatch.setattr(settings, "notification_channels", ["log", "email", "webhook"])
    types = [type(c) for c in get_active_channels()]
    assert types == [LogChannel, EmailChannel, WebhookChannel]


async def test_log_channel_always_sends():
    await LogChannel().send(target="dr@x.com", subject="s", body="b")  # não levanta


async def test_email_channel_requires_smtp(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", None)
    with pytest.raises(RuntimeError):
        await EmailChannel().send(target="dr@x.com", subject="s", body="b")


async def test_webhook_channel_requires_url(monkeypatch):
    monkeypatch.setattr(settings, "notification_webhook_url", None)
    with pytest.raises(RuntimeError):
        await WebhookChannel().send(target="dr@x.com", subject="s", body="b")


# ---------- Integração (banco) ----------
async def _register_and_create_patient(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    p = await client.post("/api/v1/patients", headers=headers,
                          json={"name": "João", "consent_given": True})
    return {"headers": headers, "patient": p.json()}


async def test_critical_checkin_records_notification(client: httpx.AsyncClient):
    ctx = await _register_and_create_patient(client)
    ph = {"X-Patient-Token": ctx["patient"]["access_token"]}
    resp = await client.post("/api/v1/patient/checkins", headers=ph,
                             json={"structured_responses": CRITICAL})
    assert resp.status_code == 201

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Notification))
        notifs = list(result.scalars().all())

    assert len(notifs) == 1
    assert notifs[0].channel is NotificationChannel.LOG
    assert notifs[0].status is NotificationStatus.SENT
    assert notifs[0].sent_at is not None
    # destino é o e-mail do médico responsável
    assert notifs[0].target == "dra.ana@clinica.com"


async def test_stable_checkin_creates_no_notification(client: httpx.AsyncClient):
    ctx = await _register_and_create_patient(client)
    ph = {"X-Patient-Token": ctx["patient"]["access_token"]}
    stable = {**CRITICAL, "mood": 8, "anxiety": 1, "slept_well": "sim",
              "sleep_hours": 8, "medication_taken": "sim", "crisis": "nao", "side_effects": "nao"}
    await client.post("/api/v1/patient/checkins", headers=ph,
                      json={"structured_responses": stable})

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Notification))
        assert list(result.scalars().all()) == []
