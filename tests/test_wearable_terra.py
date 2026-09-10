"""Integração Terra: mapeamento de payload, assinatura do webhook e fluxo de auth."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import date

import httpx

from app.core.config import settings
from app.services.wearable_provider import (
    TerraProvider,
    active_provider_info,
    get_wearable_provider,
    map_terra_records,
    terra_configured,
)

_DAILY = [{
    "metadata": {"start_time": "2026-09-09T00:00:00+00:00", "end_time": "2026-09-09T23:59:59+00:00"},
    "heart_rate_data": {"summary": {"resting_hr_bpm": 61, "avg_hrv_rmssd": 45}},
    "distance_data": {"steps": 8200},
}]
_SLEEP = [{
    "metadata": {"start_time": "2026-09-08T23:00:00+00:00", "end_time": "2026-09-09T07:00:00+00:00"},
    "sleep_durations_data": {"asleep": {"duration_asleep_state_seconds": 27000}},  # 450 min
}]


def test_map_terra_records():
    out = map_terra_records(_DAILY, _SLEEP)
    s = out[date(2026, 9, 9)]
    assert s.steps == 8200 and s.resting_hr == 61 and s.hrv_ms == 45 and s.sleep_minutes == 450


def test_map_terra_records_partial():
    # Só sono, sem daily — não quebra e preenche o que veio.
    out = map_terra_records([], _SLEEP)
    assert out[date(2026, 9, 9)].sleep_minutes == 450
    assert out[date(2026, 9, 9)].steps is None


def test_provider_selection(monkeypatch):
    monkeypatch.setattr(settings, "wearable_provider", "terra")
    monkeypatch.setattr(settings, "terra_api_key", None)
    monkeypatch.setattr(settings, "terra_dev_id", None)
    assert terra_configured() is False
    # Sem credenciais → cai no demo.
    assert type(get_wearable_provider("terra")).__name__ == "DemoProvider"
    assert active_provider_info().available is False

    monkeypatch.setattr(settings, "terra_api_key", "k")
    monkeypatch.setattr(settings, "terra_dev_id", "d")
    assert terra_configured() is True
    assert isinstance(get_wearable_provider("terra"), TerraProvider)
    assert active_provider_info().available is True


def _sign(body: bytes, secret: str) -> str:
    t = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{t}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={sig}"


async def _doctor(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5543988580825", "consent_given": True})).json()


async def test_webhook_rejects_bad_signature(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "terra_signing_secret", "segredo")
    r = await client.post("/api/v1/webhooks/terra", content=b'{"type":"auth"}',
                          headers={"terra-signature": "t=1,v1=deadbeef"})
    assert r.status_code == 401


async def test_webhook_auth_links_user_and_syncs(client: httpx.AsyncClient, monkeypatch):
    # Configura Terra + mocka as chamadas externas do provider.
    monkeypatch.setattr(settings, "wearable_provider", "terra")
    monkeypatch.setattr(settings, "terra_api_key", "k")
    monkeypatch.setattr(settings, "terra_dev_id", "d")
    monkeypatch.setattr(settings, "terra_signing_secret", "segredo")

    async def _fake_begin(self, patient, connection):
        return "https://widget.tryterra.co/session/abc"

    async def _fake_sync(self, patient, connection, days):
        return list(map_terra_records(_DAILY, _SLEEP).values())

    monkeypatch.setattr(TerraProvider, "begin_connect", _fake_begin)
    monkeypatch.setattr(TerraProvider, "sync", _fake_sync)

    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    # Paciente inicia a conexão → recebe a URL do widget (OAuth).
    c = await client.post("/api/v1/patient/wearable/connect", headers=ph)
    assert c.status_code == 200 and c.json()["connect_url"].startswith("https://widget")
    assert c.json()["connected"] is False

    # Terra confirma a autorização (webhook auth) com reference_id = id do paciente.
    body = json.dumps({
        "type": "auth",
        "user": {"user_id": "terra-user-123", "reference_id": patient["id"]},
    }).encode()
    w = await client.post("/api/v1/webhooks/terra", content=body,
                          headers={"terra-signature": _sign(body, "segredo")})
    assert w.status_code == 200

    # Agora há dados reais (do backfill mockado).
    summary = (await client.get("/api/v1/patient/wearable", headers=ph)).json()
    assert summary["connected"] is True
    assert summary["latest"]["steps"] == 8200 and summary["latest"]["sleep_minutes"] == 450
