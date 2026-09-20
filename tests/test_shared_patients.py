"""Pacientes compartilhados: dono vê todos; médico vê os seus; recepção barrada."""

from __future__ import annotations

import uuid

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


async def _second_doctor(client) -> dict:
    async with AsyncSessionLocal() as s:
        owner_user = (
            await s.execute(select(User).where(User.email == "dona@clinica.com"))
        ).scalar_one()
        member = await get_current_member(user=owner_user, session=s)
        _inv, raw = await clinic_service.create_invitation(
            s, member, InvitationCreate(email="dr.dois@clinica.com", role="doctor")
        )
        await s.commit()
    acc = await client.post("/api/v1/clinic/invitations/accept",
                            json={"token": raw, "name": "Dr. Dois", "password": "outrasenha1"})
    return {"Authorization": f"Bearer {acc.json()['access_token']}"}


async def _reception(client, tenant_id: uuid.UUID) -> dict:
    async with AsyncSessionLocal() as s:
        user = User(email="recep@clinica.com", hashed_password=hash_password("x"), role=UserRole.DOCTOR)
        s.add(user)
        await s.flush()
        s.add(Membership(user_id=user.id, tenant_id=tenant_id, role=ClinicRole.RECEPTION))
        await s.commit()
        uid = user.id
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


async def _patient(client, headers, name: str) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": name, "contact": "+5543988580825", "consent_given": True})).json()


async def test_owner_sees_all_patients(client: httpx.AsyncClient):
    owner = await _owner(client)
    tid = await _tenant_id(client, owner)
    d2 = await _second_doctor(client)

    p1 = await _patient(client, owner, "Ana P1")
    p2 = await _patient(client, d2, "Bruno P2")

    owner_list = (await client.get("/api/v1/patients", headers=owner)).json()
    d2_list = (await client.get("/api/v1/patients", headers=d2)).json()
    assert {p["name"] for p in owner_list} == {"Ana P1", "Bruno P2"}
    assert {p["name"] for p in d2_list} == {"Bruno P2"}

    # Dono abre o paciente do colega (detalhe + check-ins) sem quebrar.
    assert (await client.get(f"/api/v1/patients/{p2['id']}", headers=owner)).status_code == 200
    assert (await client.get(f"/api/v1/patients/{p2['id']}/checkins", headers=owner)).status_code == 200
    # E o segundo médico NÃO abre o paciente do dono.
    assert (await client.get(f"/api/v1/patients/{p1['id']}", headers=d2)).status_code == 404


async def test_reception_blocked_from_patients(client: httpx.AsyncClient):
    owner = await _owner(client)
    tid = await _tenant_id(client, owner)
    await _patient(client, owner, "Ana")
    rec = await _reception(client, tid)
    assert (await client.get("/api/v1/patients", headers=rec)).status_code == 403
    assert (await client.get("/api/v1/patients/attention", headers=rec)).status_code == 403
