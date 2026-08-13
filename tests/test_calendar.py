"""Calendário do paciente + check-in retroativo (responder um dia esquecido)."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

STABLE = {
    "mood": 8, "anxiety": 2, "slept_well": "sim", "sleep_hours": 8,
    "medication_taken": "sim", "crisis": "nao", "side_effects": "nao", "self_harm": "nao",
}
RISKY = {**STABLE, "mood": 1}  # humor muito baixo -> vermelho


def _sp_today():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


async def _doctor(client: httpx.AsyncClient, email: str = "dr.cal@x.com") -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "senhaforte123", "name": "Dr. Cal"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post(
        "/api/v1/patients", headers=headers,
        json={"name": "Ana", "contact": "+5511999999999", "consent_given": True},
    )).json()


async def _submit(client, ph, responses, for_date=None):
    body = {"structured_responses": responses, "free_text": None}
    if for_date is not None:
        body["for_date"] = for_date.isoformat()
    return await client.post("/api/v1/patient/checkins", headers=ph, json=body)


async def test_backfill_yesterday_and_calendar(client: httpx.AsyncClient):
    h = await _doctor(client)
    p = await _patient(client, h)
    ph = {"X-Patient-Token": p["access_token"]}
    yesterday = _sp_today() - timedelta(days=1)

    r = await _submit(client, ph, STABLE, for_date=yesterday)
    assert r.status_code == 201

    cal = (await client.get("/api/v1/patient/checkins/calendar?days=7", headers=ph)).json()
    day = {d["date"]: d for d in cal}
    y = day[yesterday.isoformat()]
    assert y["checked_in"] is True and y["mood"] == 8
    t = day[_sp_today().isoformat()]
    assert t["is_today"] is True and t["checked_in"] is False and t["can_fill"] is False


async def test_future_rejected(client: httpx.AsyncClient):
    h = await _doctor(client)
    p = await _patient(client, h)
    ph = {"X-Patient-Token": p["access_token"]}
    r = await _submit(client, ph, STABLE, for_date=_sp_today() + timedelta(days=1))
    assert r.status_code == 400


async def test_too_old_rejected(client: httpx.AsyncClient):
    h = await _doctor(client)
    p = await _patient(client, h)
    ph = {"X-Patient-Token": p["access_token"]}
    r = await _submit(client, ph, STABLE, for_date=_sp_today() - timedelta(days=8))
    assert r.status_code == 400


async def test_duplicate_day_conflict(client: httpx.AsyncClient):
    h = await _doctor(client)
    p = await _patient(client, h)
    ph = {"X-Patient-Token": p["access_token"]}
    d = _sp_today() - timedelta(days=2)
    assert (await _submit(client, ph, STABLE, for_date=d)).status_code == 201
    assert (await _submit(client, ph, STABLE, for_date=d)).status_code == 409


async def test_calendar_marks_fillable_days(client: httpx.AsyncClient):
    h = await _doctor(client)
    p = await _patient(client, h)
    ph = {"X-Patient-Token": p["access_token"]}
    cal = (await client.get("/api/v1/patient/checkins/calendar?days=3", headers=ph)).json()
    day = {d["date"]: d for d in cal}
    y = day[(_sp_today() - timedelta(days=1)).isoformat()]
    assert y["can_fill"] is True and y["checked_in"] is False


async def test_backfill_does_not_lower_current_risk(client: httpx.AsyncClient):
    h = await _doctor(client)
    p = await _patient(client, h)
    ph = {"X-Patient-Token": p["access_token"]}

    # hoje com risco alto -> paciente fica vermelho no painel
    assert (await _submit(client, ph, RISKY)).status_code == 201
    panel = (await client.get("/api/v1/patients", headers=h)).json()
    assert next(x for x in panel if x["id"] == p["id"])["current_risk"] == "red"

    # retroativo neutro de ontem NÃO pode rebaixar o risco atual
    assert (await _submit(client, ph, STABLE, for_date=_sp_today() - timedelta(days=1))).status_code == 201
    panel = (await client.get("/api/v1/patients", headers=h)).json()
    assert next(x for x in panel if x["id"] == p["id"])["current_risk"] == "red"
