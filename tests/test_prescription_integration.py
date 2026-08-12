"""Base multi-provedor de receita: escolher plataforma, conectar conta, emitir."""

from __future__ import annotations

import httpx

ITEMS = [{"name": "Alprazolam", "dose": "1mg", "instructions": "1x à noite"}]


async def _doctor(client: httpx.AsyncClient, email: str = "dr.presc@x.com") -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "senhaforte123", "name": "Dr. Presc"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_lists_providers_including_memed(client: httpx.AsyncClient):
    h = await _doctor(client)
    providers = (await client.get("/api/v1/prescriptions/providers", headers=h)).json()
    slugs = {p["slug"] for p in providers}
    assert {"none", "memed"} <= slugs
    memed = next(p for p in providers if p["slug"] == "memed")
    assert memed["legal_value"] is True and memed["requires_credential"] is True


async def test_default_integration_is_internal(client: httpx.AsyncClient):
    h = await _doctor(client)
    integ = (await client.get("/api/v1/prescriptions/integration", headers=h)).json()
    assert integ["provider"] == "none"
    assert integ["connected"] is True  # não exige credencial
    assert integ["legal_value"] is False


async def test_connect_memed_then_disconnect(client: httpx.AsyncClient):
    h = await _doctor(client)
    # escolher memed SEM token ainda -> conectado=False (falta credencial)
    r = await client.put(
        "/api/v1/prescriptions/integration", headers=h, json={"provider": "memed"}
    )
    assert r.status_code == 200
    assert r.json()["provider"] == "memed" and r.json()["connected"] is False

    # informar o token -> conectado=True
    r = await client.put(
        "/api/v1/prescriptions/integration",
        headers=h,
        json={"provider": "memed", "credential": "tok_memed_123"},
    )
    assert r.json()["connected"] is True and r.json()["legal_value"] is True

    # desconectar -> volta pro interno
    r = await client.delete("/api/v1/prescriptions/integration", headers=h)
    assert r.json()["provider"] == "none"


async def test_invalid_provider_rejected(client: httpx.AsyncClient):
    h = await _doctor(client)
    r = await client.put(
        "/api/v1/prescriptions/integration", headers=h, json={"provider": "inexistente"}
    )
    assert r.status_code == 400


async def test_issue_with_memed_pending(client: httpx.AsyncClient):
    """Com memed conectado mas integração ainda não homologada, emitir -> 503 claro."""
    h = await _doctor(client)
    await client.put(
        "/api/v1/prescriptions/integration",
        headers=h,
        json={"provider": "memed", "credential": "tok_memed_123"},
    )
    patient = (await client.post(
        "/api/v1/patients", headers=h,
        json={"name": "Ana", "contact": "+5511999999999", "consent_given": True},
    )).json()
    presc = (await client.post(
        f"/api/v1/patients/{patient['id']}/prescriptions", headers=h, json={"items": ITEMS}
    )).json()
    r = await client.post(f"/api/v1/prescriptions/{presc['id']}/issue", headers=h)
    assert r.status_code == 503
    assert "Memed" in r.json()["detail"]


async def test_issue_without_provider_uses_internal(client: httpx.AsyncClient):
    """Sem integração, a emissão cai no registro interno (sem valor legal)."""
    h = await _doctor(client)
    patient = (await client.post(
        "/api/v1/patients", headers=h,
        json={"name": "Ana", "contact": "+5511999999999", "consent_given": True},
    )).json()
    presc = (await client.post(
        f"/api/v1/patients/{patient['id']}/prescriptions", headers=h, json={"items": ITEMS}
    )).json()
    r = await client.post(f"/api/v1/prescriptions/{presc['id']}/issue", headers=h)
    assert r.status_code == 200
    assert r.json()["external_id"].startswith("internal:")
