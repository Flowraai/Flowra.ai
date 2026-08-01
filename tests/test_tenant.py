"""Testes da fundação multi-tenant (tenant por conta; herança pelo paciente)."""

from __future__ import annotations

import httpx


async def _register(client: httpx.AsyncClient, email: str, **extra) -> dict:
    body = {"email": email, "password": "senhaforte123", "name": "Dra. Ana"}
    body.update(extra)
    r = await client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_register_creates_solo_tenant(client: httpx.AsyncClient):
    headers = await _register(client, "solo@x.com")
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["tenant_id"]
    assert me["tenant_name"] == "Dra. Ana"  # sem clínica -> nome do médico


async def test_register_with_clinic_names_tenant(client: httpx.AsyncClient):
    headers = await _register(client, "clinica@x.com", clinic="Clínica Central")
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["tenant_name"] == "Clínica Central"


async def test_each_account_gets_its_own_tenant(client: httpx.AsyncClient):
    h1 = await _register(client, "a@x.com")
    h2 = await _register(client, "b@x.com")
    t1 = (await client.get("/api/v1/auth/me", headers=h1)).json()["tenant_id"]
    t2 = (await client.get("/api/v1/auth/me", headers=h2)).json()["tenant_id"]
    assert t1 and t2 and t1 != t2


async def test_patient_inherits_doctor_tenant(client: httpx.AsyncClient):
    headers = await _register(client, "dra@x.com")
    tenant_id = (await client.get("/api/v1/auth/me", headers=headers)).json()["tenant_id"]

    patient = (await client.post("/api/v1/patients", headers=headers,
                                 json={"name": "João", "consent_given": True})).json()
    assert patient["tenant_id"] == tenant_id
