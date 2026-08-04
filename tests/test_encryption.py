"""Criptografia em repouso dos campos sensíveis + guardrails de produção."""

from __future__ import annotations

import base64
import os

import httpx
import pytest
from sqlalchemy import text

from app.core import crypto
from app.core.config import Settings
from app.db.session import AsyncSessionLocal

_KEY = base64.b64encode(os.urandom(32)).decode()

CRITICAL = {
    "mood": 1, "anxiety": 9, "slept_well": "nao", "sleep_hours": 2,
    "medication_taken": "nao", "crisis": "sim", "side_effects": "sim",
}


# ---------- Unidade: cifra/decifra ----------
def test_encrypt_roundtrip(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.encryption_key", _KEY)
    cipher = crypto.encrypt("ideação suicida")
    assert cipher.startswith("enc:v1:")
    assert "ideação" not in cipher
    assert crypto.decrypt(cipher) == "ideação suicida"


def test_encrypt_passthrough_without_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.encryption_key", None)
    assert crypto.encrypt("olá") == "olá"
    # texto sem prefixo (legado/dev) é lido como está
    assert crypto.decrypt("olá") == "olá"


def test_invalid_key_raises(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.encryption_key", "chave-curta")
    with pytest.raises(ValueError):
        crypto.encrypt("x")


# ---------- Integração: dado sensível cifrado no banco ----------
async def test_sensitive_fields_encrypted_at_rest(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.encryption_key", _KEY)
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    patient = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João da Silva", "contact": "joao@ex.com", "consent_given": True})).json()
    ph = {"X-Patient-Token": patient["access_token"]}
    await client.post("/api/v1/patient/checkins", headers=ph,
                      json={"structured_responses": CRITICAL,
                            "free_text": "não aguento mais, quero me matar"})

    # No banco, o conteúdo sensível está cifrado (prefixo enc:), sem texto em claro.
    async with AsyncSessionLocal() as session:
        name_raw = await session.scalar(
            text("SELECT name FROM patients WHERE id = :id"), {"id": patient["id"]})
        contact_raw = await session.scalar(
            text("SELECT contact FROM patients WHERE id = :id"), {"id": patient["id"]})
        free_text_raw = await session.scalar(
            text("SELECT free_text FROM checkins WHERE patient_id = :id"), {"id": patient["id"]})

    assert name_raw.startswith("enc:v1:") and "João" not in name_raw
    assert contact_raw.startswith("enc:v1:") and "joao@ex.com" not in contact_raw
    assert free_text_raw.startswith("enc:v1:") and "matar" not in free_text_raw

    # Pela API (ORM decifra de forma transparente) o valor volta em claro.
    got = (await client.get(f"/api/v1/patients/{patient['id']}", headers=headers)).json()
    assert got["name"] == "João da Silva"


# ---------- Guardrails de produção ----------
def _prod(**extra) -> Settings:
    base = {
        "environment": "production", "debug": False,
        "jwt_secret_key": "um-segredo-bem-forte-de-producao",
    }
    base.update(extra)
    return Settings(**base)


def test_production_rejects_default_jwt_secret():
    with pytest.raises(RuntimeError):
        _prod(jwt_secret_key="troque-este-segredo-em-producao").enforce_production_guardrails()


def test_production_rejects_debug():
    with pytest.raises(RuntimeError):
        _prod(debug=True).enforce_production_guardrails()


def test_production_warns_without_encryption_key():
    warnings = _prod(encryption_key=None).enforce_production_guardrails()
    assert any("ENCRYPTION_KEY" in w for w in warnings)


def test_external_ai_blocked_in_production_without_dpa():
    s = _prod(llm_api_key="sk-x", free_text_analyzer="llm", ai_dpa_acknowledged=False)
    assert s.llm_available is False
    s2 = _prod(llm_api_key="sk-x", free_text_analyzer="llm", ai_dpa_acknowledged=True)
    assert s2.llm_available is True


def test_docs_disabled_in_production():
    assert _prod().docs_enabled is False
    assert Settings(environment="development").docs_enabled is True
