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


async def test_dashboard_aggregates(client: httpx.AsyncClient):
    from datetime import datetime, timedelta, timezone

    headers = await _owner(client)
    # Paciente + consulta concluída + cobrança recebida.
    p = (await client.post("/api/v1/patients", headers=headers, json={
        "name": "Ana", "contact": "+5543988580825", "consent_given": True})).json()
    # No passado recente (dentro do mês, antes de agora) para entrar no período do painel.
    when = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    appt = (await client.post(f"/api/v1/patients/{p['id']}/appointments", headers=headers,
                              json={"scheduled_at": when})).json()
    await client.patch(f"/api/v1/appointments/{appt['id']}", headers=headers,
                       json={"status": "completed"})
    ch = (await client.get(f"/api/v1/patients/{p['id']}/charges", headers=headers)).json()[0]
    await client.patch(f"/api/v1/charges/{ch['id']}", headers=headers, json={"gross_cents": 20000})
    await client.patch(f"/api/v1/charges/{ch['id']}", headers=headers,
                       json={"status": "received", "payment_method": "pix"})

    d = (await client.get("/api/v1/clinic/dashboard", headers=headers)).json()
    assert d["patients_total"] == 1 and d["doctors_total"] == 1
    assert d["appointments_completed"] == 1
    assert d["received_cents"] == 20000
    assert len(d["doctors"]) == 1
    assert d["doctors"][0]["patients"] == 1 and d["doctors"][0]["received_cents"] == 20000


async def test_rateio_split_and_totals(client: httpx.AsyncClient):
    from datetime import datetime, timedelta, timezone

    owner = await _owner(client)
    # Segundo médico via convite.
    _tid, raw = await _invite_raw("dr.rateio@x.com", "doctor")
    acc = await client.post("/api/v1/clinic/invitations/accept",
                            json={"token": raw, "name": "Dr. Rateio", "password": "outrasenha1"})
    d2 = {"Authorization": f"Bearer {acc.json()['access_token']}"}

    # Dono define 30% de rateio da clínica sobre as consultas do médico.
    members = (await client.get("/api/v1/clinic/members", headers=owner)).json()
    m = next(x for x in members if x["email"] == "dr.rateio@x.com")
    upd = await client.patch(f"/api/v1/clinic/members/{m['id']}", headers=owner,
                             json={"clinic_share_percent": 30})
    assert upd.status_code == 200 and upd.json()["clinic_share_percent"] == 30

    # Médico atende um particular de R$ 200 e recebe.
    p = (await client.post("/api/v1/patients", headers=d2, json={
        "name": "Ana", "contact": "+5543988580825", "consent_given": True})).json()
    when = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    appt = (await client.post(f"/api/v1/patients/{p['id']}/appointments", headers=d2,
                              json={"scheduled_at": when})).json()
    await client.patch(f"/api/v1/appointments/{appt['id']}", headers=d2, json={"status": "completed"})
    ch = (await client.get(f"/api/v1/patients/{p['id']}/charges", headers=d2)).json()[0]
    upd2 = await client.patch(f"/api/v1/charges/{ch['id']}", headers=d2, json={"gross_cents": 20000})
    # 70% médico, 30% clínica.
    assert upd2.json()["doctor_cents"] == 14000 and upd2.json()["clinic_cents"] == 6000
    await client.patch(f"/api/v1/charges/{ch['id']}", headers=d2,
                       json={"status": "received", "payment_method": "pix"})

    # Resumo do médico mostra a fatia da clínica.
    s = (await client.get("/api/v1/charges/summary", headers=d2)).json()
    assert s["received_cents"] == 14000 and s["clinic_received_cents"] == 6000

    # Painel do gestor consolida a fatia da clínica.
    d = (await client.get("/api/v1/clinic/dashboard", headers=owner)).json()
    assert d["clinic_received_cents"] == 6000
    stat = next(x for x in d["doctors"] if x["name"] == "Dr. Rateio")
    assert stat["received_cents"] == 14000 and stat["clinic_cents"] == 6000


async def test_owner_views_and_edits_doctor_cadastro(client: httpx.AsyncClient):
    owner = await _owner(client)
    _tid, raw = await _invite_raw("dr.cad@x.com", "doctor")
    await client.post("/api/v1/clinic/invitations/accept",
                      json={"token": raw, "name": "Dr. Cadastro", "password": "outrasenha1"})

    members = (await client.get("/api/v1/clinic/members", headers=owner)).json()
    m = next(x for x in members if x["email"] == "dr.cad@x.com")

    # Dono lê o cadastro profissional do médico.
    got = await client.get(f"/api/v1/clinic/members/{m['id']}/doctor", headers=owner)
    assert got.status_code == 200
    body = got.json()
    assert body["email"] == "dr.cad@x.com" and body["name"] == "Dr. Cadastro"

    # Dono edita especialidade, CRM e clínica.
    upd = await client.patch(f"/api/v1/clinic/members/{m['id']}/doctor", headers=owner,
                             json={"specialty": "psicologia", "council_id": "CRP 01/1234",
                                   "clinic": "Unidade Centro"})
    assert upd.status_code == 200
    assert upd.json()["specialty"] == "psicologia"
    assert upd.json()["council_id"] == "CRP 01/1234"
    assert upd.json()["clinic"] == "Unidade Centro"


async def test_doctor_cadastro_reception_and_scope_guards(client: httpx.AsyncClient):
    owner = await _owner(client)
    tid = await _tenant_id(client, owner)

    # Recepção não tem cadastro de médico → 404.
    members = (await client.get("/api/v1/clinic/members", headers=owner)).json()
    await _reception_headers(tid, "recep.cad@x.com")
    members = (await client.get("/api/v1/clinic/members", headers=owner)).json()
    rec_m = next(x for x in members if x["email"] == "recep.cad@x.com")
    r = await client.get(f"/api/v1/clinic/members/{rec_m['id']}/doctor", headers=owner)
    assert r.status_code == 404

    # Recepção não pode ler o cadastro de ninguém (só o dono).
    rec = await _reception_headers(tid, "recep.cad2@x.com")
    owner_m = next(x for x in members if x["role"] == "owner")
    assert (await client.get(f"/api/v1/clinic/members/{owner_m['id']}/doctor",
                             headers=rec)).status_code == 403


async def test_dashboard_owner_only(client: httpx.AsyncClient):
    headers = await _owner(client)
    tid = await _tenant_id(client, headers)
    rec = await _reception_headers(tid, "recep.dash@x.com")
    assert (await client.get("/api/v1/clinic/dashboard", headers=rec)).status_code == 403


async def test_duplicate_membership_conflict(client: httpx.AsyncClient):
    headers = await _owner(client)
    tid = await _tenant_id(client, headers)
    await _reception_headers(tid, "dup@x.com")
    # Convidar quem já é membro → 409.
    r = await client.post("/api/v1/clinic/invitations", headers=headers,
                          json={"email": "dup@x.com", "role": "reception"})
    assert r.status_code == 409
