"""Anotações clínicas (prontuário): criar, listar, vincular à consulta, editar, excluir."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "consent_given": True})).json()


async def test_create_list_edit_delete(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)

    r = await client.post(f"/api/v1/patients/{p['id']}/notes", headers=headers,
                          json={"kind": "diagnosis", "body": "TAG (F41.1)"})
    assert r.status_code == 201
    note = r.json()
    assert note["kind"] == "diagnosis" and note["body"] == "TAG (F41.1)"

    lst = (await client.get(f"/api/v1/patients/{p['id']}/notes", headers=headers)).json()
    assert len(lst) == 1

    upd = await client.patch(f"/api/v1/notes/{note['id']}", headers=headers,
                             json={"body": "TAG (F41.1) — ajustar dose"})
    assert upd.status_code == 200 and "ajustar dose" in upd.json()["body"]

    d = await client.delete(f"/api/v1/notes/{note['id']}", headers=headers)
    assert d.status_code == 204
    assert (await client.get(f"/api/v1/patients/{p['id']}/notes", headers=headers)).json() == []


async def test_note_linked_to_appointment(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)
    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    appt = (await client.post(f"/api/v1/patients/{p['id']}/appointments", headers=headers,
                              json={"scheduled_at": when, "kind": "consultation"})).json()

    await client.post(f"/api/v1/patients/{p['id']}/notes", headers=headers,
                      json={"kind": "note", "body": "Evolução da consulta",
                            "appointment_id": appt["id"]})
    # Filtra por consulta.
    filtered = (await client.get(
        f"/api/v1/patients/{p['id']}/notes?appointment_id={appt['id']}", headers=headers)).json()
    assert len(filtered) == 1 and filtered[0]["appointment_id"] == appt["id"]


async def test_notes_isolation(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    p = await _patient(client, headers_a)
    note = (await client.post(f"/api/v1/patients/{p['id']}/notes", headers=headers_a,
                              json={"kind": "note", "body": "sigilo"})).json()
    headers_b = await _doctor(client, email="dr.b@x.com")
    assert (await client.get(f"/api/v1/patients/{p['id']}/notes", headers=headers_b)).status_code == 404
    assert (await client.patch(f"/api/v1/notes/{note['id']}", headers=headers_b,
                               json={"body": "x"})).status_code == 404


async def test_invalid_kind_rejected(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)
    r = await client.post(f"/api/v1/patients/{p['id']}/notes", headers=headers,
                          json={"kind": "xpto", "body": "y"})
    assert r.status_code == 422
