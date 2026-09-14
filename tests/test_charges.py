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


async def test_doctor_list_and_summary(client: httpx.AsyncClient):
    headers = await _doctor(client)
    # Particular: consulta realizada, valor R$ 200, recebido via PIX.
    p1 = await _patient(client, headers, name="Ana")
    a1 = await _appointment(client, headers, p1["id"])
    await _complete(client, headers, a1["id"])
    ch1 = (await client.get(f"/api/v1/patients/{p1['id']}/charges", headers=headers)).json()[0]
    await client.patch(f"/api/v1/charges/{ch1['id']}", headers=headers, json={"gross_cents": 20000})
    await client.patch(f"/api/v1/charges/{ch1['id']}", headers=headers,
                       json={"status": "received", "payment_method": "pix"})

    # Convênio: repasse fixo R$ 90 a receber.
    plan = await _plan(client, headers, default_consultation_cents=15000)
    p2 = await _patient(client, headers, name="Bruno", health_plan_id=plan["id"])
    a2 = await _appointment(client, headers, p2["id"])
    await _complete(client, headers, a2["id"])

    # Lista do médico com nome do paciente.
    lst = (await client.get("/api/v1/charges", headers=headers)).json()
    assert len(lst) == 2
    assert {c["patient_name"] for c in lst} == {"Ana", "Bruno"}

    # Filtro por status.
    pend = (await client.get("/api/v1/charges?status=pending", headers=headers)).json()
    assert len(pend) == 1 and pend[0]["patient_name"] == "Bruno"

    # Resumo agregado.
    s = (await client.get("/api/v1/charges/summary", headers=headers)).json()
    assert s["received_cents"] == 20000 and s["to_receive_cents"] == 9000
    assert s["particular"]["received_cents"] == 20000
    assert s["convenio"]["to_receive_cents"] == 9000
    assert len(s["by_plan"]) == 2
    assert len(s["monthly"]) == 1
    assert s["monthly"][0]["received_cents"] == 20000 and s["monthly"][0]["pending_cents"] == 9000


async def test_summary_excludes_cancelled(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers)
    a = await _appointment(client, headers, p["id"])
    await _complete(client, headers, a["id"])
    ch = (await client.get(f"/api/v1/patients/{p['id']}/charges", headers=headers)).json()[0]
    await client.patch(f"/api/v1/charges/{ch['id']}", headers=headers,
                       json={"gross_cents": 10000})
    await client.patch(f"/api/v1/charges/{ch['id']}", headers=headers, json={"status": "cancelled"})
    s = (await client.get("/api/v1/charges/summary", headers=headers)).json()
    assert s["received_cents"] == 0 and s["to_receive_cents"] == 0 and s["cancelled_count"] == 1


async def test_csv_export(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p = await _patient(client, headers, name="Ana Lima")
    a = await _appointment(client, headers, p["id"])
    await _complete(client, headers, a["id"])
    ch = (await client.get(f"/api/v1/patients/{p['id']}/charges", headers=headers)).json()[0]
    await client.patch(f"/api/v1/charges/{ch['id']}", headers=headers, json={"gross_cents": 20000})
    await client.patch(f"/api/v1/charges/{ch['id']}", headers=headers,
                       json={"status": "received", "payment_method": "pix"})

    r = await client.get("/api/v1/charges/export.csv", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.text
    assert "Paciente" in body and "Repasse (R$)" in body  # cabeçalho
    assert "Ana Lima" in body and "200,00" in body        # linha com decimais pt-BR
    assert ";" in body                                    # separador do Excel pt-BR

    # Filtro por status: 'pending' não traz a cobrança já recebida.
    empty = await client.get("/api/v1/charges/export.csv?status=pending", headers=headers)
    assert "Ana Lima" not in empty.text


async def _set_pix(client, headers, key="ana@pix.com", city="São Paulo"):
    return await client.patch("/api/v1/auth/me", headers=headers,
                              json={"pix_key": key, "pix_city": city})


async def _particular_charge(client, headers, gross=15000) -> dict:
    p = await _patient(client, headers)
    a = await _appointment(client, headers, p["id"])
    await _complete(client, headers, a["id"])
    ch = (await client.get(f"/api/v1/patients/{p['id']}/charges", headers=headers)).json()[0]
    await client.patch(f"/api/v1/charges/{ch['id']}", headers=headers, json={"gross_cents": gross})
    return ch


async def test_pix_copia_e_cola(client: httpx.AsyncClient):
    headers = await _doctor(client)
    await _set_pix(client, headers)
    ch = await _particular_charge(client, headers, gross=15000)

    r = await client.get(f"/api/v1/charges/{ch['id']}/pix", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["amount_cents"] == 15000
    assert body["city"] == "São Paulo"
    payload = body["payload"]
    assert payload.startswith("000201")          # Payload Format Indicator
    assert "br.gov.bcb.pix" in payload
    assert "ana@pix.com" in payload
    assert "5406150.00" in payload                # valor R$ 150,00
    # CRC16 (CCITT-FALSE) fecha o payload: os 4 hex finais conferem.
    from app.services.pix import crc16
    assert crc16(payload[:-4]) == payload[-4:]


async def test_pix_requires_config(client: httpx.AsyncClient):
    headers = await _doctor(client)
    ch = await _particular_charge(client, headers)  # sem PIX configurado
    r = await client.get(f"/api/v1/charges/{ch['id']}/pix", headers=headers)
    assert r.status_code == 400


async def test_pix_rejects_convenio(client: httpx.AsyncClient):
    headers = await _doctor(client)
    await _set_pix(client, headers)
    plan = await _plan(client, headers, default_consultation_cents=15000)
    p = await _patient(client, headers, health_plan_id=plan["id"])
    a = await _appointment(client, headers, p["id"])
    await _complete(client, headers, a["id"])
    ch = (await client.get(f"/api/v1/patients/{p['id']}/charges", headers=headers)).json()[0]
    r = await client.get(f"/api/v1/charges/{ch['id']}/pix", headers=headers)
    assert r.status_code == 400  # convênio é pago pelo plano, não pelo paciente


async def test_pix_isolation(client: httpx.AsyncClient):
    headers = await _doctor(client)
    await _set_pix(client, headers)
    ch = await _particular_charge(client, headers)
    headers_b = await _doctor(client, email="dr.b@x.com")
    r = await client.get(f"/api/v1/charges/{ch['id']}/pix", headers=headers_b)
    assert r.status_code == 404


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
