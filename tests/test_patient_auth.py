"""Login do paciente por CPF + senha: ativação, entrada e recuperação por código."""

from __future__ import annotations

import re

import httpx

from app.core.security import valid_cpf

CPF = "11144477735"       # CPF válido (dígitos verificadores corretos)
CPF2 = "52998224725"      # outro CPF válido


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict, contact: str | None = "+5543988580825") -> dict:
    body = {"name": "João Silva", "consent_given": True}
    if contact:
        body["contact"] = contact
    return (await client.post("/api/v1/patients", headers=headers, json=body)).json()


def test_valid_cpf():
    assert valid_cpf(CPF) and valid_cpf(CPF2)
    assert not valid_cpf("11111111111")  # todos iguais
    assert not valid_cpf("12345678900")  # dígito errado
    assert not valid_cpf("123")          # curto


async def test_account_activate_and_login(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)
    onboarding = {"X-Patient-Token": p["access_token"]}

    # Conta ainda não ativada.
    acc = (await client.get("/api/v1/patient/account", headers=onboarding)).json()
    assert acc["activated"] is False and acc["has_contact"] is True and acc["name"] == "João Silva"

    # Ativa: define CPF + senha → recebe token de sessão.
    r = await client.post("/api/v1/patient/activate", headers=onboarding,
                          json={"cpf": CPF, "password": "minhasenha1"})
    assert r.status_code == 200
    session = {"X-Patient-Token": r.json()["access_token"]}

    # Token do convite deixou de valer; o de sessão vale e está ativado.
    assert (await client.get("/api/v1/patient/account", headers=onboarding)).status_code == 401
    acc2 = (await client.get("/api/v1/patient/account", headers=session)).json()
    assert acc2["activated"] is True

    # Reativar é bloqueado.
    again = await client.post("/api/v1/patient/activate", headers=session,
                              json={"cpf": CPF, "password": "outrasenha"})
    assert again.status_code == 409

    # Login por CPF + senha.
    ok = await client.post("/api/v1/patient/login", json={"cpf": CPF, "password": "minhasenha1"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    # A nova sessão acessa o app.
    s2 = {"X-Patient-Token": ok.json()["access_token"]}
    assert (await client.get("/api/v1/patient/today", headers=s2)).status_code == 200

    # Senha errada → 401 genérico.
    bad = await client.post("/api/v1/patient/login", json={"cpf": CPF, "password": "errada"})
    assert bad.status_code == 401


async def test_activate_rejects_invalid_cpf(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)
    onboarding = {"X-Patient-Token": p["access_token"]}
    r = await client.post("/api/v1/patient/activate", headers=onboarding,
                          json={"cpf": "12345678900", "password": "minhasenha1"})
    assert r.status_code == 422


async def test_cpf_is_unique(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p1 = await _patient(client, headers)
    p2 = await _patient(client, headers)
    await client.post("/api/v1/patient/activate",
                      headers={"X-Patient-Token": p1["access_token"]},
                      json={"cpf": CPF, "password": "senha12345"})
    dup = await client.post("/api/v1/patient/activate",
                            headers={"X-Patient-Token": p2["access_token"]},
                            json={"cpf": CPF, "password": "senha12345"})
    assert dup.status_code == 409


async def test_forgot_and_reset_password(client: httpx.AsyncClient, monkeypatch):
    sent: list[str] = []

    async def _capture(session, patient, subject, body):
        sent.append(body)
        return True

    monkeypatch.setattr("app.api.routes.patient_auth.deliver_to_patient", _capture)

    headers = await _doctor(client)
    p = await _patient(client, headers)
    await client.post("/api/v1/patient/activate",
                      headers={"X-Patient-Token": p["access_token"]},
                      json={"cpf": CPF, "password": "senhaantiga1"})

    # Esqueci a senha → código enviado ao contato (resposta genérica).
    r = await client.post("/api/v1/patient/forgot-password", json={"cpf": CPF})
    assert r.status_code == 200
    assert sent, "deveria ter enviado o código"
    code = re.search(r"\b(\d{6})\b", sent[-1]).group(1)

    # Código errado → 400.
    bad = await client.post("/api/v1/patient/reset-password",
                            json={"cpf": CPF, "code": "000000", "new_password": "novasenha1"})
    assert bad.status_code == 400

    # Código certo → redefine e entra.
    ok = await client.post("/api/v1/patient/reset-password",
                           json={"cpf": CPF, "code": code, "new_password": "novasenha1"})
    assert ok.status_code == 200 and ok.json()["access_token"]

    # Nova senha funciona; a antiga não.
    assert (await client.post("/api/v1/patient/login",
            json={"cpf": CPF, "password": "novasenha1"})).status_code == 200
    assert (await client.post("/api/v1/patient/login",
            json={"cpf": CPF, "password": "senhaantiga1"})).status_code == 401


async def test_forgot_unknown_cpf_is_generic(client: httpx.AsyncClient):
    # CPF válido mas sem conta → resposta genérica 200 (anti-enumeração).
    r = await client.post("/api/v1/patient/forgot-password", json={"cpf": CPF2})
    assert r.status_code == 200
