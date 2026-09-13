"""Faturamento de convênio em lotes e conciliação (recebido / glosado)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _plan(client, headers, **over) -> dict:
    body = {"name": "Unimed", "payout_type": "fixed", "payout_value_cents": 9000,
            "default_consultation_cents": 15000}
    body.update(over)
    return (await client.post("/api/v1/health-plans", headers=headers, json=body)).json()


async def _patient(client, headers, name="João", **over) -> dict:
    body = {"name": name, "contact": "+5543988580825", "consent_given": True}
    body.update(over)
    return (await client.post("/api/v1/patients", headers=headers, json=body)).json()


async def _completed_charge(client, headers, patient_id: str) -> dict:
    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    appt = (await client.post(f"/api/v1/patients/{patient_id}/appointments", headers=headers,
                              json={"scheduled_at": when})).json()
    await client.patch(f"/api/v1/appointments/{appt['id']}", headers=headers, json={"status": "completed"})
    return (await client.get(f"/api/v1/patients/{patient_id}/charges", headers=headers)).json()[0]


async def test_create_batch_bills_pending_convenio_charges(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers)
    p1 = await _patient(client, headers, name="A", health_plan_id=plan["id"])
    p2 = await _patient(client, headers, name="B", health_plan_id=plan["id"])
    await _completed_charge(client, headers, p1["id"])
    await _completed_charge(client, headers, p2["id"])

    r = await client.post("/api/v1/billing-batches", headers=headers,
                          json={"health_plan_id": plan["id"], "reference": "2026-09"})
    assert r.status_code == 201
    batch = r.json()
    assert batch["charge_count"] == 2 and batch["billed_cents"] == 18000
    assert batch["health_plan_name"] == "Unimed" and batch["status"] == "open"
    assert all(c["status"] == "billed" and c["batch_id"] == batch["id"] for c in batch["charges"])


async def test_reconcile_received_and_denied(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers)
    p1 = await _patient(client, headers, name="A", health_plan_id=plan["id"])
    p2 = await _patient(client, headers, name="B", health_plan_id=plan["id"])
    c1 = await _completed_charge(client, headers, p1["id"])
    c2 = await _completed_charge(client, headers, p2["id"])
    batch = (await client.post("/api/v1/billing-batches", headers=headers,
                               json={"health_plan_id": plan["id"]})).json()

    # Concilia: c1 recebido, c2 glosado (com motivo).
    await client.patch(f"/api/v1/charges/{c1['id']}", headers=headers,
                       json={"status": "received", "payment_method": "convenio"})
    await client.patch(f"/api/v1/charges/{c2['id']}", headers=headers,
                       json={"status": "denied", "notes": "Guia sem autorização"})

    detail = (await client.get(f"/api/v1/billing-batches/{batch['id']}", headers=headers)).json()
    assert detail["received_cents"] == 9000 and detail["denied_cents"] == 9000
    assert detail["billed_cents"] == 0
    denied = next(c for c in detail["charges"] if c["id"] == c2["id"])
    assert denied["status"] == "denied" and denied["notes"] == "Guia sem autorização"


async def test_summary_counts_billed_as_receivable_and_denied_apart(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers)
    p1 = await _patient(client, headers, name="A", health_plan_id=plan["id"])
    p2 = await _patient(client, headers, name="B", health_plan_id=plan["id"])
    c1 = await _completed_charge(client, headers, p1["id"])
    await _completed_charge(client, headers, p2["id"])
    await client.post("/api/v1/billing-batches", headers=headers, json={"health_plan_id": plan["id"]})

    # Ambas faturadas (billed) → ainda contam como "a receber".
    s = (await client.get("/api/v1/charges/summary", headers=headers)).json()
    assert s["to_receive_cents"] == 18000 and s["received_cents"] == 0

    # Glosa uma → sai do a receber e entra em glosado.
    await client.patch(f"/api/v1/charges/{c1['id']}", headers=headers,
                       json={"status": "denied", "notes": "glosa"})
    s = (await client.get("/api/v1/charges/summary", headers=headers)).json()
    assert s["to_receive_cents"] == 9000
    assert s["denied_cents"] == 9000 and s["denied_count"] == 1


async def test_empty_batch_rejected_and_isolation(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers)  # sem cobranças pendentes
    r = await client.post("/api/v1/billing-batches", headers=headers,
                          json={"health_plan_id": plan["id"]})
    assert r.status_code == 400

    # Isolamento: outro médico não vê nem cria lote no convênio alheio.
    headers_b = await _doctor(client, email="dr.b@x.com")
    assert (await client.post("/api/v1/billing-batches", headers=headers_b,
                              json={"health_plan_id": plan["id"]})).status_code == 404
    assert (await client.get("/api/v1/billing-batches", headers=headers_b)).json() == []


async def test_close_batch(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers)
    p1 = await _patient(client, headers, name="A", health_plan_id=plan["id"])
    await _completed_charge(client, headers, p1["id"])
    batch = (await client.post("/api/v1/billing-batches", headers=headers,
                               json={"health_plan_id": plan["id"]})).json()
    r = await client.post(f"/api/v1/billing-batches/{batch['id']}/close", headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "closed"
