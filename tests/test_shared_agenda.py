"""Agenda compartilhada: dono/recepção veem todos os médicos; médico só os seus."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.api.deps import get_current_member
from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import ClinicRole, UserRole
from app.models.membership import Membership
from app.models.user import User
from app.schemas.clinic import InvitationCreate
from app.services import clinic_service


async def _owner(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dona@clinica.com", "password": "senhaforte123", "name": "Dra. Dona"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _tenant_id(client, headers) -> uuid.UUID:
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    return uuid.UUID(me["tenant_id"])


async def _invite_doctor(email: str) -> str:
    async with AsyncSessionLocal() as s:
        owner_user = (
            await s.execute(select(User).where(User.email == "dona@clinica.com"))
        ).scalar_one()
        member = await get_current_member(user=owner_user, session=s)
        _inv, raw = await clinic_service.create_invitation(
            s, member, InvitationCreate(email=email, role="doctor")
        )
        await s.commit()
    return raw


async def _reception_headers(tenant_id: uuid.UUID, email: str) -> dict:
    async with AsyncSessionLocal() as s:
        user = User(email=email, hashed_password=hash_password("x"), role=UserRole.DOCTOR)
        s.add(user)
        await s.flush()
        s.add(Membership(user_id=user.id, tenant_id=tenant_id, role=ClinicRole.RECEPTION))
        await s.commit()
        uid = user.id
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


async def _patient(client, headers, name: str) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": name, "contact": "+5543988580825", "consent_given": True})).json()


async def _appointment(client, headers, patient_id: str) -> dict:
    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    return (await client.post(f"/api/v1/patients/{patient_id}/appointments", headers=headers,
                              json={"scheduled_at": when})).json()


async def test_shared_agenda_scope_by_role(client: httpx.AsyncClient):
    owner = await _owner(client)
    tid = await _tenant_id(client, owner)

    # Segundo médico via convite.
    raw = await _invite_doctor("dr.dois@clinica.com")
    acc = await client.post("/api/v1/clinic/invitations/accept",
                            json={"token": raw, "name": "Dr. Dois", "password": "outrasenha1"})
    d2 = {"Authorization": f"Bearer {acc.json()['access_token']}"}

    # Cada médico com um paciente e uma consulta.
    p1 = await _patient(client, owner, "Ana P1")
    await _appointment(client, owner, p1["id"])
    p2 = await _patient(client, d2, "Bruno P2")
    await _appointment(client, d2, p2["id"])

    # Dono (gestão) vê os dois; segundo médico vê só o seu.
    owner_up = (await client.get("/api/v1/appointments/upcoming", headers=owner)).json()
    d2_up = (await client.get("/api/v1/appointments/upcoming", headers=d2)).json()
    assert len(owner_up) == 2
    assert len(d2_up) == 1 and d2_up[0]["patient_name"] == "Bruno P2"

    # Recepção vê a agenda inteira, com os nomes, sem acessar dado clínico.
    rec = await _reception_headers(tid, "recep@clinica.com")
    rec_up = (await client.get("/api/v1/appointments/upcoming", headers=rec)).json()
    assert len(rec_up) == 2
    assert {a["patient_name"] for a in rec_up} == {"Ana P1", "Bruno P2"}
    # E não lê o painel clínico.
    assert (await client.get("/api/v1/patients", headers=rec)).status_code in (401, 403)


async def test_reception_can_manage_appointment(client: httpx.AsyncClient):
    owner = await _owner(client)
    tid = await _tenant_id(client, owner)
    p1 = await _patient(client, owner, "Ana")
    appt = await _appointment(client, owner, p1["id"])

    rec = await _reception_headers(tid, "recep2@clinica.com")
    # Recepção confirma a consulta.
    r = await client.patch(f"/api/v1/appointments/{appt['id']}", headers=rec,
                           json={"status": "confirmed"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
