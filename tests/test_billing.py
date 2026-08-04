"""Assinatura: gestão de planos (admin), checkout, gate de acesso e webhook."""

from __future__ import annotations

import httpx

from app.core.config import settings

ADMIN_EMAIL = "admin@flowraai.com.br"


async def _doctor(client: httpx.AsyncClient, email: str = "dr.sub@x.com") -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "senhaforte123", "name": "Dr. Sub"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _make_plan(client: httpx.AsyncClient, admin: dict, **over) -> dict:
    body = {"name": "Essencial", "price_cents": 14990, "cycle": "monthly", **over}
    r = await client.post("/api/v1/admin/plans", headers=admin, json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- Admin: gestão de planos ----------
async def test_only_admin_manages_plans(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", [ADMIN_EMAIL])
    admin = await _doctor(client, email=ADMIN_EMAIL)
    common = await _doctor(client, email="comum@x.com")

    # admin cria
    plan = await _make_plan(client, admin)
    assert plan["price_cents"] == 14990

    # médico comum não acessa a área de admin
    r = await client.get("/api/v1/admin/plans", headers=common)
    assert r.status_code == 403

    # admin edita o preço
    r = await client.patch(
        f"/api/v1/admin/plans/{plan['id']}", headers=admin, json={"price_cents": 19990}
    )
    assert r.status_code == 200 and r.json()["price_cents"] == 19990


async def test_active_plans_visible_to_doctor(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", [ADMIN_EMAIL])
    admin = await _doctor(client, email=ADMIN_EMAIL)
    await _make_plan(client, admin, name="Ativo", active=True)
    await _make_plan(client, admin, name="Inativo", active=False)

    doctor = await _doctor(client)
    plans = (await client.get("/api/v1/billing/plans", headers=doctor)).json()
    names = [p["name"] for p in plans]
    assert "Ativo" in names and "Inativo" not in names


# ---------- Assinatura (provedor manual) ----------
async def test_subscribe_manual_activates(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", [ADMIN_EMAIL])
    admin = await _doctor(client, email=ADMIN_EMAIL)
    plan = await _make_plan(client, admin)

    doctor = await _doctor(client)
    r = await client.post(
        "/api/v1/billing/subscribe",
        headers=doctor,
        json={"plan_id": plan["id"], "cpf_cnpj": "111.444.777-35"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active"

    sub = (await client.get("/api/v1/billing/subscription", headers=doctor)).json()
    assert sub["status"] == "active"
    assert sub["plan"]["name"] == "Essencial"


async def test_subscribe_rejects_invalid_cpf(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", [ADMIN_EMAIL])
    admin = await _doctor(client, email=ADMIN_EMAIL)
    plan = await _make_plan(client, admin)
    doctor = await _doctor(client)
    r = await client.post(
        "/api/v1/billing/subscribe",
        headers=doctor,
        json={"plan_id": plan["id"], "cpf_cnpj": "123"},
    )
    assert r.status_code == 422


# ---------- Gate de acesso ----------
async def test_gate_blocks_without_subscription_then_allows(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", [ADMIN_EMAIL])
    monkeypatch.setattr(settings, "billing_enabled", True)
    admin = await _doctor(client, email=ADMIN_EMAIL)
    plan = await _make_plan(client, admin)

    doctor = await _doctor(client)
    # sem assinatura -> 402 nas telas clínicas
    r = await client.get("/api/v1/patients", headers=doctor)
    assert r.status_code == 402

    # assina -> libera
    await client.post(
        "/api/v1/billing/subscribe",
        headers=doctor,
        json={"plan_id": plan["id"], "cpf_cnpj": "111.444.777-35"},
    )
    r = await client.get("/api/v1/patients", headers=doctor)
    assert r.status_code == 200


async def test_admin_bypasses_gate(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", [ADMIN_EMAIL])
    monkeypatch.setattr(settings, "billing_enabled", True)
    admin = await _doctor(client, email=ADMIN_EMAIL)
    # admin não tem assinatura, mas acessa as telas clínicas
    r = await client.get("/api/v1/patients", headers=admin)
    assert r.status_code == 200


async def test_gate_noop_when_billing_disabled(client: httpx.AsyncClient):
    # billing_enabled=false (default): sem assinatura, ainda acessa (comportamento atual)
    doctor = await _doctor(client)
    r = await client.get("/api/v1/patients", headers=doctor)
    assert r.status_code == 200


# ---------- Webhook ----------
async def test_webhook_requires_token(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "asaas_webhook_token", "segredo-webhook")
    # sem header -> 401
    r = await client.post("/api/v1/billing/webhook", json={"event": "PAYMENT_CONFIRMED"})
    assert r.status_code == 401
    # header errado -> 401
    r = await client.post(
        "/api/v1/billing/webhook",
        headers={"asaas-access-token": "errado"},
        json={"event": "PAYMENT_CONFIRMED"},
    )
    assert r.status_code == 401


async def test_webhook_overdue_blocks_access(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", [ADMIN_EMAIL])
    monkeypatch.setattr(settings, "billing_enabled", True)
    monkeypatch.setattr(settings, "asaas_webhook_token", "segredo-webhook")
    admin = await _doctor(client, email=ADMIN_EMAIL)
    plan = await _make_plan(client, admin)
    doctor = await _doctor(client)
    await client.post(
        "/api/v1/billing/subscribe",
        headers=doctor,
        json={"plan_id": plan["id"], "cpf_cnpj": "111.444.777-35"},
    )
    # força um gateway_subscription_id conhecido para o webhook encontrar
    from sqlalchemy import update

    from app.db.session import AsyncSessionLocal
    from app.models.subscription import Subscription

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Subscription).values(gateway_subscription_id="sub_test_123")
        )
        await session.commit()

    # evento de vencimento -> bloqueia
    r = await client.post(
        "/api/v1/billing/webhook",
        headers={"asaas-access-token": "segredo-webhook"},
        json={"event": "PAYMENT_OVERDUE", "payment": {"subscription": "sub_test_123"}},
    )
    assert r.status_code == 200
    blocked = await client.get("/api/v1/patients", headers=doctor)
    assert blocked.status_code == 402
