"""Metas (limiares) de escala por paciente e o sinal 'fora da meta' no painel."""

from __future__ import annotations

import httpx


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict) -> dict:
    return (await client.post("/api/v1/patients", headers=headers, json={
        "name": "João", "contact": "+5543988580825", "consent_given": True})).json()


async def test_set_list_update_delete_target(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    pid = patient["id"]

    # Define meta PHQ-9 ≤ 9 (remissão).
    r = await client.put(f"/api/v1/patients/{pid}/scale-targets/phq9", headers=headers,
                         json={"target_score": 9})
    assert r.status_code == 200
    assert r.json()["target_score"] == 9 and r.json()["scale_name"].startswith("PHQ-9")

    # Aparece na listagem.
    lst = (await client.get(f"/api/v1/patients/{pid}/scale-targets", headers=headers)).json()
    assert len(lst) == 1 and lst[0]["scale_code"] == "phq9"

    # Atualiza (upsert, não duplica).
    await client.put(f"/api/v1/patients/{pid}/scale-targets/phq9", headers=headers,
                     json={"target_score": 5})
    lst = (await client.get(f"/api/v1/patients/{pid}/scale-targets", headers=headers)).json()
    assert len(lst) == 1 and lst[0]["target_score"] == 5

    # Remove.
    d = await client.delete(f"/api/v1/patients/{pid}/scale-targets/phq9", headers=headers)
    assert d.status_code == 204
    assert (await client.get(f"/api/v1/patients/{pid}/scale-targets", headers=headers)).json() == []


async def test_target_validation(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    pid = patient["id"]
    # Escala desconhecida.
    r = await client.put(f"/api/v1/patients/{pid}/scale-targets/xyz", headers=headers,
                         json={"target_score": 5})
    assert r.status_code == 404
    # Acima do máximo do PHQ-9 (27).
    r = await client.put(f"/api/v1/patients/{pid}/scale-targets/phq9", headers=headers,
                         json={"target_score": 28})
    assert r.status_code == 422


async def test_target_isolated_per_doctor(client: httpx.AsyncClient):
    headers_a = await _doctor(client)
    patient = await _patient(client, headers_a)
    pid = patient["id"]
    headers_b = await _doctor(client, email="dr.b@x.com")
    assert (await client.put(f"/api/v1/patients/{pid}/scale-targets/phq9", headers=headers_b,
                             json={"target_score": 9})).status_code == 404
    assert (await client.get(f"/api/v1/patients/{pid}/scale-targets", headers=headers_b)).status_code == 404


async def test_off_target_surfaces_in_attention(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    pid = patient["id"]
    ph = {"X-Patient-Token": patient["access_token"]}

    # Meta: GAD-7 ≤ 5. Paciente responde 12 (acima da meta), sem item de risco.
    await client.put(f"/api/v1/patients/{pid}/scale-targets/gad7", headers=headers,
                     json={"target_score": 5})
    req = (await client.post(f"/api/v1/patients/{pid}/scales", headers=headers,
                             json={"scale_code": "gad7"})).json()
    await client.post(f"/api/v1/patient/scales/{req['id']}", headers=ph,
                      json={"answers": [2, 2, 2, 2, 2, 1, 1]})  # 12

    items = (await client.get("/api/v1/patients/attention", headers=headers)).json()
    it = next(i for i in items if i["id"] == pid)
    target_reasons = [r for r in it["reasons"] if r["code"] == "target"]
    assert target_reasons and "12 > 5" in target_reasons[0]["label"]


async def test_within_target_no_attention(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    pid = patient["id"]
    ph = {"X-Patient-Token": patient["access_token"]}

    # Meta: GAD-7 ≤ 10. Paciente responde 7 (dentro da meta) → sem sinal.
    await client.put(f"/api/v1/patients/{pid}/scale-targets/gad7", headers=headers,
                     json={"target_score": 10})
    req = (await client.post(f"/api/v1/patients/{pid}/scales", headers=headers,
                             json={"scale_code": "gad7"})).json()
    await client.post(f"/api/v1/patient/scales/{req['id']}", headers=ph,
                      json={"answers": [1, 1, 1, 1, 1, 1, 1]})  # 7

    items = (await client.get("/api/v1/patients/attention", headers=headers)).json()
    assert all(i["id"] != pid for i in items)
