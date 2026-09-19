"""Marco 1 (clínica): Membership, papel do usuário no tenant e escopo por papel."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
from sqlalchemy import select

from app.api.deps import CurrentMember, get_current_member, scope_query
from app.db.session import AsyncSessionLocal
from app.models.enums import ClinicRole
from app.models.membership import Membership
from app.models.patient import Patient
from app.models.user import User


async def _register(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_register_creates_owner_membership(client: httpx.AsyncClient):
    headers = await _register(client)
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    async with AsyncSessionLocal() as s:
        rows = list(
            (
                await s.execute(
                    select(Membership).where(Membership.tenant_id == uuid.UUID(me["tenant_id"]))
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].role is ClinicRole.OWNER and rows[0].is_active


async def test_get_current_member_resolves(client: httpx.AsyncClient):
    await _register(client, email="dra.ana@clinica.com")
    async with AsyncSessionLocal() as s:
        user = (
            await s.execute(select(User).where(User.email == "dra.ana@clinica.com"))
        ).scalar_one()
        member = await get_current_member(user=user, session=s)
    assert member.role is ClinicRole.OWNER
    assert member.doctor is not None            # o dono tem perfil clínico (é médico)
    assert member.is_management and member.can_read_clinical


def test_scope_query_by_role():
    tenant_id = uuid.uuid4()
    doctor = SimpleNamespace(id=uuid.uuid4())

    doc = CurrentMember(user=None, tenant_id=tenant_id, role=ClinicRole.DOCTOR, doctor=doctor)
    q = str(scope_query(select(Patient), Patient, doc))
    assert "doctor_id" in q and "tenant_id" not in q.split("WHERE")[-1]

    owner = CurrentMember(user=None, tenant_id=tenant_id, role=ClinicRole.OWNER, doctor=doctor)
    q2 = str(scope_query(select(Patient), Patient, owner))
    assert "tenant_id" in q2.split("WHERE")[-1]

    # Recepção (sem perfil clínico) também vê o tenant inteiro; não lê clínico.
    recep = CurrentMember(user=None, tenant_id=tenant_id, role=ClinicRole.RECEPTION, doctor=None)
    assert not recep.can_read_clinical
    q3 = str(scope_query(select(Patient), Patient, recep))
    assert "tenant_id" in q3.split("WHERE")[-1]
