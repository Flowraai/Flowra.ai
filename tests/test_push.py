"""Testes de push: registro de device token e envio (provedor log)."""

from __future__ import annotations

import httpx
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.device_token import DeviceToken


async def _doctor(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient_token(client: httpx.AsyncClient, headers: dict) -> str:
    p = (await client.post("/api/v1/patients", headers=headers,
                           json={"name": "João", "consent_given": True})).json()
    return p["access_token"]


async def _device_count() -> int:
    async with AsyncSessionLocal() as s:
        return await s.scalar(select(func.count()).select_from(DeviceToken))


async def test_patient_registers_device(client: httpx.AsyncClient):
    headers = await _doctor(client)
    ph = {"X-Patient-Token": await _patient_token(client, headers)}
    r = await client.post("/api/v1/patient/devices", headers=ph,
                          json={"token": "ExponentPushToken[abc]", "platform": "ios"})
    assert r.status_code == 201
    assert r.json()["platform"] == "ios" and r.json()["is_active"] is True


async def test_doctor_test_push(client: httpx.AsyncClient):
    headers = await _doctor(client)
    await client.post("/api/v1/devices", headers=headers,
                      json={"token": "ExponentPushToken[doc]", "platform": "android"})
    r = await client.post("/api/v1/notifications/test-push", headers=headers)
    assert r.status_code == 200
    assert r.json()["sent"] == 1


async def test_reregister_same_token_is_idempotent(client: httpx.AsyncClient):
    headers = await _doctor(client)
    body = {"token": "ExponentPushToken[dup]", "platform": "ios"}
    await client.post("/api/v1/devices", headers=headers, json=body)
    await client.post("/api/v1/devices", headers=headers, json={**body, "platform": "android"})
    assert await _device_count() == 1


async def test_unregister_stops_push(client: httpx.AsyncClient):
    headers = await _doctor(client)
    body = {"token": "ExponentPushToken[off]", "platform": "ios"}
    await client.post("/api/v1/devices", headers=headers, json=body)
    await client.post("/api/v1/devices/unregister", headers=headers, json=body)
    r = await client.post("/api/v1/notifications/test-push", headers=headers)
    assert r.json()["sent"] == 0


async def test_test_push_without_devices(client: httpx.AsyncClient):
    headers = await _doctor(client)
    r = await client.post("/api/v1/notifications/test-push", headers=headers)
    assert r.status_code == 200 and r.json()["sent"] == 0
