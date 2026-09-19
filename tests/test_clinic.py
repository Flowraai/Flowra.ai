"""Marco 2 (clínica): convites e gestão de equipe (só o dono)."""

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


async def _owner(client: httpx.AsyncClient, email: str = "dona@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Dona"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _tenant_id(client, headers) -> uuid.UUID:
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    return uuid.UUID(me["tenant_id"])


async def _invite_raw(email: str, role: str, can_view_finance: bool = False) -> tuple[uuid.UUID, str]:
    """Cria um convite pela camada de serviço para obter o token cru (para aceitar)."""
    async with AsyncSessionLocal() as s:
        owner_user = (
            await s.execute(select(User).where(User.email == "dona@clinica.com"))
        ).scalar_one()
        member = await get_current_member(user=owner_user, session=s)
        invite, raw = await clinic_service.create_invitation(
            s, member, InvitationCreate(email=email, role=role, can_view_finance=can_view_finance)
        )
        tid = invite.tenant_id
        await s.commit()
    return tid, raw


async def _reception_headers(tenant_id: uuid.UUID, email: str) -> dict:
    async with AsyncSessionLocal() as s:
        user = User(email=email, hashed_password=hash_password("x"), role=UserRole.DOCTOR)
        s.add(user)
        await s.flush()
        s.add(Membership(user_id=user.id, tenant_id=tenant_id, role=ClinicRole.RECEPTION))
        await s.commit()
        uid = user.id
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


async def test_owner_creates_and_lists_invitation(client: httpx.AsyncClient):
    headers = await _owner(client)
    r = await client.post("/api/v1/clinic/invitations", headers=headers,
                          json={"email": "novo.medico@x.com", "role": "doctor"})
    assert r.status_code == 201 and r.json()["role"] == "doctor"
    lst = (await client.get("/api/v1/clinic/invitations", headers=headers)).json()
    assert len(lst) == 1 and lst[0]["accepted_at"] is None


async def test_non_owner_cannot_manage(client: httpx.AsyncClient):
    headers = await _owner(client)
    tid = await _tenant_id(client, headers)
    rec = await _reception_headers(tid, "recep@x.com")
    assert (await client.get("/api/v1/clinic/members", headers=rec)).status_code == 403
    assert (await client.post("/api/v1/clinic/invitations", headers=rec,
                              json={"email": "a@b.com", "role": "doctor"})).status_code == 403


async def test_accept_invitation_creates_doctor_and_logs_in(client: httpx.AsyncClient):
    headers = await _owner(client)
    await _tenant_id(client, headers)
    _tid, raw = await _invite_raw("dr.novo@x.com", "doctor")

    r = await client.post("/api/v1/clinic/invitations/accept",
                          json={"token": raw, "name": "Dr. Novo", "password": "outrasenha1"})
    assert r.status_code == 200
    new_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = (await client.get("/api/v1/auth/me", headers=new_headers)).json()
    assert me["name"] == "Dr. Novo"

    members = (await client.get("/api/v1/clinic/members", headers=headers)).json()
    assert len(members) == 2
    assert {m["role"] for m in members} == {"owner", "doctor"}


async def test_invalid_token_rejected(client: httpx.AsyncClient):
    r = await client.post("/api/v1/clinic/invitations/accept",
                          json={"token": "nao-existe", "name": "X", "password": "12345678"})
    assert r.status_code == 400


async def test_owner_toggles_reception_finance(client: httpx.AsyncClient):
    headers = await _owner(client)
    tid = await _tenant_id(client, headers)
    rec = await _reception_headers(tid, "recep.fin@x.com")
    # Sem permissão: 403 no financeiro.
    assert (await client.get("/api/v1/charges", headers=rec)).status_code == 403

    members = (await client.get("/api/v1/clinic/members", headers=headers)).json()
    rec_m = next(m for m in members if m["email"] == "recep.fin@x.com")
    upd = await client.patch(f"/api/v1/clinic/members/{rec_m['id']}", headers=headers,
                             json={"can_view_finance": True})
    assert upd.status_code == 200 and upd.json()["can_view_finance"] is True
    # Agora enxerga o financeiro.
    assert (await client.get("/api/v1/charges", headers=rec)).status_code == 200


async def test_cannot_edit_owner(client: httpx.AsyncClient):
    headers = await _owner(client)
    members = (await client.get("/api/v1/clinic/members", headers=headers)).json()
    owner_m = next(m for m in members if m["role"] == "owner")
    r = await client.patch(f"/api/v1/clinic/members/{owner_m['id']}", headers=headers,
                           json={"is_active": False})
    assert r.status_code == 400


async def test_duplicate_membership_conflict(client: httpx.AsyncClient):
    headers = await _owner(client)
    tid = await _tenant_id(client, headers)
    await _reception_headers(tid, "dup@x.com")
    # Convidar quem já é membro → 409.
    r = await client.post("/api/v1/clinic/invitations", headers=headers,
                          json={"email": "dup@x.com", "role": "reception"})
    assert r.status_code == 409
