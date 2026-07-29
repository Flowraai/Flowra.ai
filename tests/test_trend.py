"""Testes do risco por tendência (unitário puro + integração)."""

from __future__ import annotations

import httpx

from app.models.enums import RiskLevel
from app.protocol import psychiatry as P
from app.risk.trend import CheckInPoint, assess_trend


def _p(level: RiskLevel, mood: int | None = None, medication: str | None = None) -> CheckInPoint:
    resp: dict = {}
    if mood is not None:
        resp[P.Q_MOOD] = mood
    if medication is not None:
        resp[P.Q_MEDICATION] = medication
    return CheckInPoint(level=level, responses=resp)


# ---------- Unitário ----------
def test_insufficient_history_is_green():
    assert assess_trend([_p(RiskLevel.RED, mood=1)]).level is RiskLevel.GREEN


def test_stable_history_is_green():
    pts = [_p(RiskLevel.GREEN, mood=8, medication=P.YES)] * 3
    assert assess_trend(pts).level is RiskLevel.GREEN


def test_sustained_elevated_is_orange():
    pts = [_p(RiskLevel.YELLOW), _p(RiskLevel.YELLOW), _p(RiskLevel.YELLOW)]
    result = assess_trend(pts)
    assert result.level is RiskLevel.ORANGE
    assert any("sustentado" in r for r in result.reasons)


def test_declining_mood_is_orange():
    # mais recente -> mais antigo: 4 < 6 < 8 (humor caindo)
    pts = [_p(RiskLevel.GREEN, mood=4), _p(RiskLevel.GREEN, mood=6), _p(RiskLevel.GREEN, mood=8)]
    result = assess_trend(pts)
    assert result.level is RiskLevel.ORANGE
    assert any("queda" in r for r in result.reasons)


def test_repeated_nonadherence_is_orange():
    pts = [
        _p(RiskLevel.GREEN, medication=P.NO),
        _p(RiskLevel.GREEN, medication=P.PARTIAL),
        _p(RiskLevel.GREEN, medication=P.YES),
    ]
    result = assess_trend(pts)
    assert result.level is RiskLevel.ORANGE
    assert any("adesão" in r for r in result.reasons)


# ---------- Integração ----------
async def _patient(client: httpx.AsyncClient) -> tuple[dict, str]:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    p = await client.post("/api/v1/patients", headers=headers,
                          json={"name": "João", "consent_given": True})
    return headers, p.json()["access_token"]


def _responses(mood: int) -> dict:
    return {
        P.Q_MOOD: mood, P.Q_ANXIETY: 2, P.Q_SLEPT_WELL: "sim", P.Q_SLEEP_HOURS: 8,
        P.Q_MEDICATION: "sim", P.Q_CRISIS: "nao", P.Q_SIDE_EFFECTS: "nao",
    }


async def test_declining_mood_escalates_patient_risk(client: httpx.AsyncClient):
    headers, token = await _patient(client)
    ph = {"X-Patient-Token": token}

    # Três check-ins com humor caindo (8 -> 7 -> 6); cada um é verde isoladamente.
    for mood in (8, 7, 6):
        r = await client.post("/api/v1/patient/checkins", headers=ph,
                              json={"structured_responses": _responses(mood)})
        assert r.status_code == 201

    # O paciente fica laranja pela TENDÊNCIA, mesmo com o último check-in verde.
    panel = (await client.get("/api/v1/patients", headers=headers)).json()
    assert panel[0]["current_risk"] == "orange"
    assert panel[0]["open_alerts"] >= 1

    history = (await client.get(
        f"/api/v1/patients/{panel[0]['id']}/checkins", headers=headers)).json()
    assert history[0]["risk_level"] == "green"  # o check-in em si é verde
