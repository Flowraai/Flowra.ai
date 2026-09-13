"""Convênios (planos de saúde do paciente) e o vínculo particular × convênio."""

from __future__ import annotations

import httpx


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _plan(client, headers, **over) -> dict:
    body = {"name": "Unimed", "payout_type": "fixed", "payout_value_cents": 9000}
    body.update(over)
    return (await client.post("/api/v1/health-plans", headers=headers, json=body)).json()


async def test_create_list_update_deactivate_plan(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers)
    assert plan["payout_type"] == "fixed" and plan["payout_value_cents"] == 9000 and plan["active"]

    plans = (await client.get("/api/v1/health-plans", headers=headers)).json()
    assert len(plans) == 1

    # Atualiza para percentual.
    upd = await client.patch(f"/api/v1/health-plans/{plan['id']}", headers=headers, json={
        "payout_type": "percentage", "payout_percent": 70, "default_consultation_cents": 15000})
    assert upd.status_code == 200 and upd.json()["payout_percent"] == 70

    # Inativa (soft-delete): some da lista padrão, aparece com include_inactive.
    d = await client.delete(f"/api/v1/health-plans/{plan['id']}", headers=headers)
    assert d.status_code == 204
    assert (await client.get("/api/v1/health-plans", headers=headers)).json() == []
    all_plans = (await client.get("/api/v1/health-plans?include_inactive=true", headers=headers)).json()
    assert len(all_plans) == 1 and all_plans[0]["active"] is False


async def test_payout_rule_validation(client: httpx.AsyncClient):
    headers = await _doctor(client)
    # fixed sem valor → 422.
    r = await client.post("/api/v1/health-plans", headers=headers,
                          json={"name": "X", "payout_type": "fixed"})
    assert r.status_code == 422
    # percentage sem percent/valor de referência → 422.
    r = await client.post("/api/v1/health-plans", headers=headers,
                          json={"name": "Y", "payout_type": "percentage", "payout_percent": 50})
    assert r.status_code == 422


async def test_patch_breaking_rule_rejected(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers)
    # Trocar para percentage sem informar percent quebra a regra → 422.
    r = await client.patch(f"/api/v1/health-plans/{plan['id']}", headers=headers,
                           json={"payout_type": "percentage"})
    assert r.status_code == 422


async def test_patient_linked_to_plan_and_back_to_particular(client: httpx.AsyncClient):
    headers = await _doctor(client)
    plan = await _plan(client, headers)

    # Cria paciente já no convênio, com carteirinha.
    created = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5543988580825", "consent_given": True,
        "health_plan_id": plan["id"], "insurance_card": "1234567890"})).json()
    assert created["health_plan_id"] == plan["id"]
    assert created["health_plan"]["name"] == "Unimed"
    assert created["insurance_card"] == "1234567890"

    # Torna particular (health_plan_id = null).
    upd = await client.patch(f"/api/v1/patients/{created['id']}", headers=headers,
                             json={"health_plan_id": None})
    assert upd.status_code == 200 and upd.json()["health_plan_id"] is None
    assert upd.json()["health_plan"] is None


async def test_cannot_link_other_doctors_plan(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    headers_b = await _doctor(client, email="dr.b@x.com")
    plan_b = await _plan(client, headers_b)
    # Médico A tenta usar convênio do médico B → 404.
    r = await client.post("/api/v1/patients", headers=headers_a, json={
        "name": "Maria", "contact": "+5543988580825", "consent_given": True,
        "health_plan_id": plan_b["id"]})
    assert r.status_code == 404


async def test_plan_isolated_per_doctor(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    plan = await _plan(client, headers_a)
    headers_b = await _doctor(client, email="dr.b@x.com")
    assert (await client.patch(f"/api/v1/health-plans/{plan['id']}", headers=headers_b,
                               json={"name": "Hack"})).status_code == 404
    assert (await client.get("/api/v1/health-plans", headers=headers_b)).json() == []
