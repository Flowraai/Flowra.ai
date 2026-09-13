"""Atestados e declarações: emissão, listagem, validação e isolamento."""

from __future__ import annotations

import httpx


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "consent_given": True})).json()


async def test_emit_afastamento_and_read(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)
    r = await client.post(f"/api/v1/patients/{p['id']}/certificates", headers=headers,
                          json={"kind": "afastamento", "days": 3, "start_date": "2026-09-13", "cid": "F41.1"})
    assert r.status_code == 201
    cert = r.json()
    assert cert["kind"] == "afastamento" and cert["days"] == 3 and cert["cid"] == "F41.1"

    got = (await client.get(f"/api/v1/certificates/{cert['id']}", headers=headers)).json()
    assert got["cid"] == "F41.1"  # decifra corretamente

    lst = (await client.get(f"/api/v1/patients/{p['id']}/certificates", headers=headers)).json()
    assert len(lst) == 1


async def test_afastamento_requires_days(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)
    r = await client.post(f"/api/v1/patients/{p['id']}/certificates", headers=headers,
                          json={"kind": "afastamento"})
    assert r.status_code == 400


async def test_declaracao_comparecimento(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)
    r = await client.post(f"/api/v1/patients/{p['id']}/certificates", headers=headers,
                          json={"kind": "comparecimento", "start_date": "2026-09-13"})
    assert r.status_code == 201 and r.json()["kind"] == "comparecimento"


async def test_invalid_kind(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)
    r = await client.post(f"/api/v1/patients/{p['id']}/certificates", headers=headers,
                          json={"kind": "xpto"})
    assert r.status_code == 422


async def test_certificate_isolation(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    p = await _patient(client, headers_a)
    cert = (await client.post(f"/api/v1/patients/{p['id']}/certificates", headers=headers_a,
                              json={"kind": "comparecimento"})).json()
    headers_b = await _doctor(client, email="dr.b@x.com")
    assert (await client.get(f"/api/v1/certificates/{cert['id']}", headers=headers_b)).status_code == 404
    assert (await client.get(f"/api/v1/patients/{p['id']}/certificates", headers=headers_b)).status_code == 404
