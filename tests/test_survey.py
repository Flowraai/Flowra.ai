"""Editor da pesquisa do médico: editar/adicionar/remover/reordenar + emoji."""

from __future__ import annotations

import httpx


async def _doctor(client: httpx.AsyncClient, email: str = "dr.survey@x.com") -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "senhaforte123", "name": "Dr. Survey"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _by_code(survey: dict, code: str) -> dict:
    return next(q for q in survey["questions"] if q["code"] == code)


async def test_survey_has_protected_safety_questions(client: httpx.AsyncClient):
    h = await _doctor(client)
    survey = (await client.get("/api/v1/survey", headers=h)).json()
    codes = {q["code"] for q in survey["questions"]}
    assert {"mood", "anxiety", "self_harm", "crisis", "medication_taken"} <= codes
    assert _by_code(survey, "self_harm")["protected"] is True
    assert _by_code(survey, "mood")["protected"] is False


async def test_edit_text_and_toggle_emoji(client: httpx.AsyncClient):
    h = await _doctor(client)
    survey = (await client.get("/api/v1/survey", headers=h)).json()
    mood = _by_code(survey, "mood")

    # editar o texto
    r = await client.patch(
        f"/api/v1/survey/questions/{mood['id']}", headers=h,
        json={"text": "Como está seu ânimo hoje?"},
    )
    assert r.status_code == 200
    assert _by_code(r.json(), "mood")["text"] == "Como está seu ânimo hoje?"

    # trocar 0–10 por emoji
    r = await client.patch(
        f"/api/v1/survey/questions/{mood['id']}", headers=h, json={"scale_style": "emoji"}
    )
    opts = _by_code(r.json(), "mood")["options"]
    assert opts["scale_style"] == "emoji"
    assert len(opts["emojis"]) == 5 and opts["emojis"][0]["value"] == 0


async def test_add_custom_and_delete(client: httpx.AsyncClient):
    h = await _doctor(client)
    r = await client.post(
        "/api/v1/survey/questions", headers=h,
        json={"text": "Bebeu álcool hoje?", "type": "boolean", "options": {"choices": ["sim", "nao"]}},
    )
    assert r.status_code == 201
    survey = r.json()
    custom = next(q for q in survey["questions"] if q["text"] == "Bebeu álcool hoje?")
    assert custom["code"].startswith("custom_")

    r = await client.delete(f"/api/v1/survey/questions/{custom['id']}", headers=h)
    assert all(q["id"] != custom["id"] for q in r.json()["questions"])


async def test_cannot_delete_protected(client: httpx.AsyncClient):
    h = await _doctor(client)
    survey = (await client.get("/api/v1/survey", headers=h)).json()
    self_harm = _by_code(survey, "self_harm")
    r = await client.delete(f"/api/v1/survey/questions/{self_harm['id']}", headers=h)
    assert r.status_code == 400


async def test_edit_reflects_for_patient_and_checkin_with_emoji(client: httpx.AsyncClient):
    """Editar a pesquisa reflete no protocolo do paciente; check-in por emoji funciona."""
    h = await _doctor(client)
    # médico ativa emoji no humor
    survey = (await client.get("/api/v1/survey", headers=h)).json()
    mood = _by_code(survey, "mood")
    await client.patch(
        f"/api/v1/survey/questions/{mood['id']}", headers=h, json={"scale_style": "emoji"}
    )
    # cria paciente (usa a cópia editada) e olha o protocolo pela ótica do paciente
    patient = (await client.post(
        "/api/v1/patients", headers=h,
        json={"name": "Ana", "contact": "+5511999999999", "consent_given": True},
    )).json()
    ph = {"X-Patient-Token": patient["access_token"]}
    proto = (await client.get("/api/v1/patient/protocol", headers=ph)).json()
    pmood = next(q for q in proto["questions"] if q["code"] == "mood")
    assert pmood["options"]["scale_style"] == "emoji"

    # check-in enviando o valor numérico (mapeado pelo emoji) — risco intacto
    r = await client.post("/api/v1/patient/checkins", headers=ph, json={
        "structured_responses": {
            "mood": 8, "anxiety": 2, "slept_well": "sim", "sleep_hours": 7,
            "medication_taken": "sim", "crisis": "nao", "side_effects": "nao", "self_harm": "nao",
        },
        "free_text": None,
    })
    assert r.status_code == 201


async def test_reorder(client: httpx.AsyncClient):
    h = await _doctor(client)
    survey = (await client.get("/api/v1/survey", headers=h)).json()
    ids = [q["id"] for q in survey["questions"]]
    reversed_ids = list(reversed(ids))
    r = await client.post("/api/v1/survey/reorder", headers=h, json={"order": reversed_ids})
    new_order = [q["id"] for q in sorted(r.json()["questions"], key=lambda x: x["position"])]
    assert new_order == reversed_ids
