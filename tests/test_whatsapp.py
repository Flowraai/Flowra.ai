"""Testes do canal WhatsApp (Meta Cloud API) e do destino por canal."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.enums import NotificationChannel, NotificationStatus
from app.models.notification import Notification
from app.services.notification_channels import WhatsAppChannel, get_active_channels
from app.services.notifications import target_for_channel

CRITICAL = {
    "mood": 1, "anxiety": 9, "slept_well": "nao", "sleep_hours": 2,
    "medication_taken": "nao", "crisis": "sim", "side_effects": "sim",
}


# ---------- Unitário: payload ----------
def test_build_text_payload(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_template_name", None)
    payload = WhatsAppChannel.build_payload("+55 (11) 98888-7777", "Assunto", "Corpo")
    assert payload["to"] == "5511988887777"  # só dígitos
    assert payload["type"] == "text"
    assert "Assunto" in payload["text"]["body"] and "Corpo" in payload["text"]["body"]


def test_build_template_payload(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_template_name", "flowra_alerta")
    monkeypatch.setattr(settings, "whatsapp_template_lang", "pt_BR")
    payload = WhatsAppChannel.build_payload("5511988887777", "Assunto", "Corpo")
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "flowra_alerta"
    assert payload["template"]["language"]["code"] == "pt_BR"
    assert payload["template"]["components"][0]["parameters"][0]["text"] == "Corpo"


async def test_send_without_config_raises(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", None)
    monkeypatch.setattr(settings, "whatsapp_access_token", None)
    with pytest.raises(RuntimeError):
        await WhatsAppChannel().send(target="5511988887777", subject="s", body="b")


def test_factory_includes_whatsapp(monkeypatch):
    monkeypatch.setattr(settings, "notification_channels", ["whatsapp"])
    channels = get_active_channels()
    assert len(channels) == 1 and isinstance(channels[0], WhatsAppChannel)


# ---------- Unitário: destino por canal ----------
def test_target_for_channel_whatsapp_uses_phone():
    assert target_for_channel(NotificationChannel.WHATSAPP, "a@x.com", "+5511") == "+5511"


def test_target_for_channel_others_use_email():
    assert target_for_channel(NotificationChannel.EMAIL, "a@x.com", "+5511") == "a@x.com"
    assert target_for_channel(NotificationChannel.LOG, "a@x.com", None) == "a@x.com"


# ---------- Integração: registro por canal no alerta ----------
async def _register(client: httpx.AsyncClient, **extra) -> dict:
    body = {"email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"}
    body.update(extra)
    r = await client.post("/api/v1/auth/register", json=body)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _critical_checkin(client: httpx.AsyncClient, headers: dict) -> None:
    p = (await client.post("/api/v1/patients", headers=headers,
                           json={"name": "João", "consent_given": True})).json()
    await client.post("/api/v1/patient/checkins",
                      headers={"X-Patient-Token": p["access_token"]},
                      json={"structured_responses": CRITICAL})


async def _notifs_by_channel() -> dict[str, Notification]:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(Notification))).scalars().all()
        return {n.channel.value: n for n in rows}


async def test_whatsapp_alert_targets_phone_and_reports_config_failure(
    client: httpx.AsyncClient, monkeypatch
):
    monkeypatch.setattr(settings, "notification_channels", ["log", "whatsapp"])
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", None)  # sem credenciais
    headers = await _register(client, notification_phone="+5511988887777")
    await _critical_checkin(client, headers)

    notifs = await _notifs_by_channel()
    assert notifs["log"].status is NotificationStatus.SENT
    # WhatsApp mira o telefone, mas falha por falta de credenciais (config).
    assert notifs["whatsapp"].status is NotificationStatus.FAILED
    assert notifs["whatsapp"].target == "+5511988887777"


async def test_whatsapp_without_phone_fails_no_contact(
    client: httpx.AsyncClient, monkeypatch
):
    monkeypatch.setattr(settings, "notification_channels", ["whatsapp"])
    headers = await _register(client)  # médico sem notification_phone
    await _critical_checkin(client, headers)

    notifs = await _notifs_by_channel()
    assert notifs["whatsapp"].status is NotificationStatus.FAILED
    assert "sem contato" in notifs["whatsapp"].error
