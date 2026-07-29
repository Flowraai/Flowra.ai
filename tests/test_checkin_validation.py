"""Testes da validação das respostas do check-in contra o protocolo."""

from __future__ import annotations

import httpx

from app.models.protocol import ProtocolQuestion
from app.protocol import psychiatry as P
from app.protocol.validation import validate_responses


def _questions() -> list[ProtocolQuestion]:
    return [
        ProtocolQuestion(
            code=q.code, category=q.category, text=q.text, type=q.type,
            position=q.position, required=q.required, options=q.options,
        )
        for q in P.PSYCHIATRY_QUESTIONS
    ]


def _valid_responses() -> dict:
    return {
        P.Q_MOOD: 8, P.Q_ANXIETY: 2, P.Q_SLEPT_WELL: "sim", P.Q_SLEEP_HOURS: 8,
        P.Q_MEDICATION: "sim", P.Q_CRISIS: "nao", P.Q_SIDE_EFFECTS: "nao",
    }


# ---------- Unitários ----------
def test_valid_responses_have_no_errors():
    assert validate_responses(_questions(), _valid_responses()) == []


def test_missing_required_is_reported():
    r = _valid_responses()
    del r[P.Q_MOOD]
    errors = validate_responses(_questions(), r)
    assert any(e.code == P.Q_MOOD and "obrigat" in e.message for e in errors)


def test_scale_out_of_range_is_reported():
    r = _valid_responses()
    r[P.Q_MOOD] = 11
    errors = validate_responses(_questions(), r)
    assert any(e.code == P.Q_MOOD and "máximo" in e.message for e in errors)


def test_invalid_choice_is_reported():
    r = _valid_responses()
    r[P.Q_MEDICATION] = "talvez"
    errors = validate_responses(_questions(), r)
    assert any(e.code == P.Q_MEDICATION for e in errors)


def test_non_integer_sleep_hours_is_reported():
    r = _valid_responses()
    r[P.Q_SLEEP_HOURS] = 7.5
    errors = validate_responses(_questions(), r)
    assert any(e.code == P.Q_SLEEP_HOURS and "inteiro" in e.message for e in errors)


def test_unknown_code_is_reported():
    r = _valid_responses()
    r["bebida"] = "café"
    errors = validate_responses(_questions(), r)
    assert any(e.code == "bebida" for e in errors)


def test_free_text_question_is_not_required_in_structured():
    # A pergunta free_text não entra em structured_responses e não gera erro.
    assert validate_responses(_questions(), _valid_responses()) == []


def test_boolean_accepts_native_bool():
    r = _valid_responses()
    r[P.Q_CRISIS] = True
    assert validate_responses(_questions(), r) == []


def test_scale_accepts_numeric_string():
    r = _valid_responses()
    r[P.Q_MOOD] = "8"
    assert validate_responses(_questions(), r) == []


# ---------- Integração ----------
async def _patient_token(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    p = await client.post("/api/v1/patients", headers=headers,
                          json={"name": "João", "consent_given": True})
    return p.json()["access_token"]


async def test_submit_invalid_checkin_returns_422(client: httpx.AsyncClient):
    ph = {"X-Patient-Token": await _patient_token(client)}
    # falta obrigatórios + valor fora de escala + pergunta desconhecida
    resp = await client.post("/api/v1/patient/checkins", headers=ph, json={
        "structured_responses": {"mood": 99, "foo": "bar"}})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["errors"]
    codes = {e["code"] for e in detail["errors"]}
    assert "mood" in codes and "foo" in codes


async def test_submit_valid_checkin_succeeds(client: httpx.AsyncClient):
    ph = {"X-Patient-Token": await _patient_token(client)}
    resp = await client.post("/api/v1/patient/checkins", headers=ph,
                             json={"structured_responses": _valid_responses()})
    assert resp.status_code == 201
