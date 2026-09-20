"""Equipe de cuidado: vários profissionais atendem o mesmo paciente."""

from __future__ import annotations


import httpx
from sqlalchemy import select

from app.api.deps import get_current_member
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.schemas.clinic import InvitationCreate
from app.services import clinic_service


async def _owner(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dona@clinica.com", "password": "senhaforte123", "name": "Dra. Dona"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _second_doctor(client) -> tuple[dict, str]:
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
    headers = {"Authorization": f"Bearer {acc.json()['access_token']}"}
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    return headers, me["id"]  # id = doctor id


async def _patient(client, headers, name: str) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": name, "contact": "+5543988580825", "consent_given": True})).json()


async def test_care_team_grants_access(client: httpx.AsyncClient):
    owner = await _owner(client)
    d2, d2_id = await _second_doctor(client)
    p = await _patient(client, owner, "Ana")

    # Antes: o segundo médico não vê nem abre o paciente.
    assert p["id"] not in {x["id"] for x in (await client.get("/api/v1/patients", headers=d2)).json()}
    assert (await client.get(f"/api/v1/patients/{p['id']}", headers=d2)).status_code == 404

    # Responsável adiciona o segundo médico à equipe.
    add = await client.post(f"/api/v1/patients/{p['id']}/care-team", headers=owner,
                            json={"doctor_id": d2_id})
    assert add.status_code == 201
    roles = {m["is_primary"] for m in add.json()}
    assert roles == {True, False} and len(add.json()) == 2

    # Agora o segundo médico vê, abre e lê o prontuário do paciente.
    assert p["id"] in {x["id"] for x in (await client.get("/api/v1/patients", headers=d2)).json()}
    assert (await client.get(f"/api/v1/patients/{p['id']}", headers=d2)).status_code == 200
    assert (await client.get(f"/api/v1/patients/{p['id']}/checkins", headers=d2)).status_code == 200
    assert (await client.get(f"/api/v1/patients/{p['id']}/notes", headers=d2)).status_code == 200


async def test_care_team_management_rules(client: httpx.AsyncClient):
    owner = await _owner(client)
    d2, d2_id = await _second_doctor(client)
    p = await _patient(client, owner, "Bruno")
    primary_id = p["doctor_id"]

    await client.post(f"/api/v1/patients/{p['id']}/care-team", headers=owner, json={"doctor_id": d2_id})

    # Não dá para remover o responsável primário.
    r = await client.delete(f"/api/v1/patients/{p['id']}/care-team/{primary_id}", headers=owner)
    assert r.status_code == 400

    # Um membro não-primário não gerencia a equipe.
    assert (await client.post(f"/api/v1/patients/{p['id']}/care-team", headers=d2,
                              json={"doctor_id": d2_id})).status_code == 404

    # O responsável/gestão remove o segundo médico; ele perde o acesso.
    rem = await client.delete(f"/api/v1/patients/{p['id']}/care-team/{d2_id}", headers=owner)
    assert rem.status_code == 204
    assert (await client.get(f"/api/v1/patients/{p['id']}", headers=d2)).status_code == 404


async def test_create_patient_makes_primary_member(client: httpx.AsyncClient):
    owner = await _owner(client)
    p = await _patient(client, owner, "Carla")
    team = (await client.get(f"/api/v1/patients/{p['id']}/care-team", headers=owner)).json()
    assert len(team) == 1 and team[0]["is_primary"] is True
