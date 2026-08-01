"""Testes de exames (solicitação, disponibilização + aviso, visão do paciente)."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.exam import Exam


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5511999999999", "consent_given": True})).json()


async def _exam(client: httpx.AsyncClient, headers: dict, patient_id: str) -> dict:
    return (await client.post(f"/api/v1/patients/{patient_id}/exams", headers=headers,
                              json={"name": "Hemograma"})).json()


async def test_create_and_patient_sees(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    exam = await _exam(client, headers, patient["id"])
    assert exam["status"] == "requested"

    mine = (await client.get("/api/v1/patient/exams",
            headers={"X-Patient-Token": patient["access_token"]})).json()
    assert len(mine) == 1 and mine[0]["name"] == "Hemograma"


async def test_mark_available_notifies_and_shows_result(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    exam = await _exam(client, headers, patient["id"])

    r = await client.patch(f"/api/v1/exams/{exam['id']}", headers=headers,
                           json={"status": "available", "result_url": "https://x/r.pdf"})
    assert r.status_code == 200
    assert r.json()["status"] == "available"
    assert r.json()["available_at"] is not None
    assert r.json()["result_url"] == "https://x/r.pdf"

    # avisou o paciente uma vez (notified_at persistido)
    async with AsyncSessionLocal() as session:
        e = (await session.execute(select(Exam).where(Exam.id == uuid.UUID(exam["id"])))).scalar_one()
        assert e.notified_at is not None


async def test_exam_isolation(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient(client, headers_a)
    exam = await _exam(client, headers_a, patient["id"])
    headers_b = await _doctor(client, email="dr.b@x.com")

    r = await client.patch(f"/api/v1/exams/{exam['id']}", headers=headers_b,
                           json={"status": "available"})
    assert r.status_code == 404
