"""Lançamentos financeiros por consulta: geração ao concluir, repasse, receber."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _plan(client, headers, **over) -> dict:
    body = {"name": "Unimed", "payout_type": "fixed", "payout_value_cents": 9000}
    body.update(over)
    return (await client.post("/api/v1/health-plans", headers=headers, json=body)).json()


async def _patient(client, headers, **over) -> dict:
    body = {"name": "João", "contact": "+5543988580825", "consent_given": True}
    body.update(over)
    return (await client.post("/api/v1/patients", headers=headers, json=body)).json()


async def _appointment(client, headers, patient_id: str) -> dict:
    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    return (await client.post(f"/api/v1/patients/{patient_id}/appointments", headers=headers,
                              json={"scheduled_at": when})).json()


async def _complete(client, headers, appt_id: str):
    return await client.patch(f"/api/v1/appointments/{appt_id}", headers=headers,
                              json={"status": "completed"})


async def test_particular_charge_created_on_completion(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)  # particular
    appt = await _appointment(client, headers, patient["id"])
    await _complete(client, headers, appt["id"])

    charges = (await client.get(f"/api/v1/patients/{patient['id']}/charges", headers=headers)).json()
    assert len(charges) == 1
    c = charges[0]
    assert c["kind"] == "particular" and c["status"] == "pending"
    assert c["gross_cents"] == 0 and c["doctor_cents"] == 0  # médico ajusta depois


async def test_convenio_charge_uses_payout_rule(client: httpx.AsyncClient):
    headers = await _doctor(client)
    # Fixo: repasse R$ 90 independentemente do valor de referência R$ 150.
    plan = await _plan(client, headers, default_consultation_cents=15000)
    patient = await _patient(client, headers, health_plan_id=plan["id"])
    appt = await _appointment(client, headers, patient["id"])
    await _complete(client, headers, appt["id"])

    c = (await client.get(f"/api/v1/patients/{patient['id']}/charges", headers=headers)).json()[0]
    assert c["kind"] == "convenio"
    assert c["gross_cents"] == 15000 and c["doctor_cents"] == 9000


async def test_percentage_payout(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers, payout_type="percentage", payout_value_cents=None,
                       payout_percent=70, default_consultation_cents=15000)
    patient = await _patient(client, headers, health_plan_id=plan["id"])
    appt = await _appointment(client, headers, patient["id"])
    await _complete(client, headers, appt["id"])
    c = (await client.get(f"/api/v1/patients/{patient['id']}/charges", headers=headers)).json()[0]
    assert c["gross_cents"] == 15000 and c["doctor_cents"] == 10500  # 70% de 150


async def test_completion_is_idempotent(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appointment(client, headers, patient["id"])
    await _complete(client, headers, appt["id"])
    # Remarca e conclui de novo — não deve duplicar o lançamento.
    await client.patch(f"/api/v1/appointments/{appt['id']}", headers=headers, json={"status": "scheduled"})
    await _complete(client, headers, appt["id"])
    charges = (await client.get(f"/api/v1/patients/{patient['id']}/charges", headers=headers)).json()
    assert len(charges) == 1


async def test_edit_value_recomputes_and_mark_received(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)  # particular
    appt = await _appointment(client, headers, patient["id"])
    await _complete(client, headers, appt["id"])
    charge = (await client.get(f"/api/v1/patients/{patient['id']}/charges", headers=headers)).json()[0]

    # Define o valor da consulta particular: repasse acompanha (solo).
    upd = await client.patch(f"/api/v1/charges/{charge['id']}", headers=headers,
                             json={"gross_cents": 20000})
    assert upd.status_code == 200
    assert upd.json()["gross_cents"] == 20000 and upd.json()["doctor_cents"] == 20000

    # Marca recebido via PIX.
    rec = await client.patch(f"/api/v1/charges/{charge['id']}", headers=headers,
                             json={"status": "received", "payment_method": "pix"})
    assert rec.json()["status"] == "received" and rec.json()["payment_method"] == "pix"
    assert rec.json()["received_at"] is not None


async def test_percentage_recompute_on_edit(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers, payout_type="percentage", payout_value_cents=None,
                       payout_percent=50, default_consultation_cents=10000)
    patient = await _patient(client, headers, health_plan_id=plan["id"])
    appt = await _appointment(client, headers, patient["id"])
    await _complete(client, headers, appt["id"])
    charge = (await client.get(f"/api/v1/patients/{patient['id']}/charges", headers=headers)).json()[0]
    # Ajusta o valor cheio → repasse recalcula (50%).
    upd = await client.patch(f"/api/v1/charges/{charge['id']}", headers=headers,
                             json={"gross_cents": 20000})
    assert upd.json()["doctor_cents"] == 10000


async def test_manual_generate_and_isolation(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    appt = await _appointment(client, headers, patient["id"])
    # Gera manualmente (consulta ainda não concluída).
    gen = await client.post(f"/api/v1/appointments/{appt['id']}/charge", headers=headers)
    assert gen.status_code == 201

    headers_b = await _doctor(client, email="dr.b@x.com")
    assert (await client.get(f"/api/v1/patients/{patient['id']}/charges", headers=headers_b)).status_code == 404
    assert (await client.patch(f"/api/v1/charges/{gen.json()['id']}", headers=headers_b,
                               json={"status": "received"})).status_code == 404
