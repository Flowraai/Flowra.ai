"""Marco 1 (clínica): Membership, papel do usuário no tenant e escopo por papel."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
from sqlalchemy import select

from app.api.deps import CurrentMember, get_current_member, scope_query
from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import ClinicRole, UserRole
from app.models.membership import Membership
from app.models.patient import Patient
from app.models.user import User


async def _reception_headers(tenant_id: uuid.UUID, email: str, can_view_finance: bool) -> dict:
    """Cria um usuário de recepção no tenant e devolve o header com o token."""
    async with AsyncSessionLocal() as s:
        user = User(email=email, hashed_password=hash_password("x"), role=UserRole.DOCTOR)
        s.add(user)
        await s.flush()
        s.add(Membership(
            user_id=user.id, tenant_id=tenant_id,
            role=ClinicRole.RECEPTION, can_view_finance=can_view_finance,
        ))
        await s.commit()
        uid = user.id
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


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


def test_sees_finance_by_role():
    tid = uuid.uuid4()
    owner = CurrentMember(user=None, tenant_id=tid, role=ClinicRole.OWNER, doctor=None)
    doctor = CurrentMember(user=None, tenant_id=tid, role=ClinicRole.DOCTOR, doctor=None)
    rec_off = CurrentMember(user=None, tenant_id=tid, role=ClinicRole.RECEPTION, doctor=None)
    rec_on = CurrentMember(
        user=None, tenant_id=tid, role=ClinicRole.RECEPTION, doctor=None, can_view_finance=True
    )
    assert owner.sees_finance and doctor.sees_finance
    assert not rec_off.sees_finance and rec_on.sees_finance


async def test_reception_finance_gate(client: httpx.AsyncClient):
    owner = await _register(client)
    me = (await client.get("/api/v1/auth/me", headers=owner)).json()
    tid = uuid.UUID(me["tenant_id"])

    # Sem permissão de financeiro: 403 no painel de cobranças.
    rec_off = await _reception_headers(tid, "recep.off@a.com", can_view_finance=False)
    assert (await client.get("/api/v1/charges", headers=rec_off)).status_code == 403

    # Com permissão: enxerga o financeiro da clínica (lista, ainda que vazia).
    rec_on = await _reception_headers(tid, "recep.on@a.com", can_view_finance=True)
    r = await client.get("/api/v1/charges", headers=rec_on)
    assert r.status_code == 200 and isinstance(r.json(), list)


async def test_session_owner_has_doctor(client: httpx.AsyncClient):
    owner = await _register(client)
    s = (await client.get("/api/v1/auth/session", headers=owner)).json()
    assert s["role"] == "owner" and s["name"] == "Dra. Ana" and s["doctor"] is not None


async def test_session_works_for_reception(client: httpx.AsyncClient):
    owner = await _register(client)
    me = (await client.get("/api/v1/auth/me", headers=owner)).json()
    tid = uuid.UUID(me["tenant_id"])
    rec = await _reception_headers(tid, "recep.session@a.com", can_view_finance=False)
    # /me exige perfil médico — recepção não passa.
    assert (await client.get("/api/v1/auth/me", headers=rec)).status_code in (401, 403)
    # /session funciona para qualquer papel.
    s = await client.get("/api/v1/auth/session", headers=rec)
    assert s.status_code == 200
    body = s.json()
    assert body["role"] == "reception" and body["doctor"] is None


async def test_reception_blocked_from_clinical(client: httpx.AsyncClient):
    owner = await _register(client)
    me = (await client.get("/api/v1/auth/me", headers=owner)).json()
    tid = uuid.UUID(me["tenant_id"])
    rec = await _reception_headers(tid, "recep.clin@a.com", can_view_finance=True)
    # /patients ainda exige perfil médico — recepção não lê dado clínico.
    assert (await client.get("/api/v1/patients", headers=rec)).status_code in (401, 403)
