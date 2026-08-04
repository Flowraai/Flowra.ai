"""Testes de anexos (upload/download com controle de acesso) e áudio no check-in."""

from __future__ import annotations

import httpx

STABLE = {
    "mood": 8, "anxiety": 2, "slept_well": "sim", "sleep_hours": 8,
    "medication_taken": "sim", "crisis": "nao", "side_effects": "nao",
}

PNG = b"\x89PNG\r\n\x1a\n" + b"conteudo-falso-de-imagem" * 4


async def _doctor(client: httpx.AsyncClient, email: str = "dra.ana@clinica.com") -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: httpx.AsyncClient, headers: dict, name: str = "João") -> dict:
    return (await client.post("/api/v1/patients", headers=headers,
                              json={"name": name, "consent_given": True})).json()


async def test_patient_upload_and_download(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    up = await client.post("/api/v1/patient/attachments", headers=ph,
                           files={"file": ("foto.png", PNG, "image/png")})
    assert up.status_code == 201
    body = up.json()
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(PNG)
    assert body["url"] == f"/api/v1/attachments/{body['id']}"

    down = await client.get(body["url"], headers=ph)
    assert down.status_code == 200
    assert down.content == PNG
    assert down.headers["content-type"].startswith("image/png")


async def test_download_denied_for_other_patient(client: httpx.AsyncClient):
    headers = await _doctor(client)
    p1 = await _patient(client, headers, name="Ana")
    p2 = await _patient(client, headers, name="Bia")

    up = await client.post("/api/v1/patient/attachments",
                           headers={"X-Patient-Token": p1["access_token"]},
                           files={"file": ("x.png", PNG, "image/png")})
    url = up.json()["url"]

    # outro paciente não acessa (404 para não revelar existência)
    r = await client.get(url, headers={"X-Patient-Token": p2["access_token"]})
    assert r.status_code == 404
    # sem credencial também não
    assert (await client.get(url)).status_code == 404


async def test_owning_doctor_can_download_but_other_doctor_cannot(client: httpx.AsyncClient):
    headers = await _doctor(client)
    other = await _doctor(client, email="dr.outro@clinica.com")
    patient = await _patient(client, headers)

    up = await client.post("/api/v1/patient/attachments",
                           headers={"X-Patient-Token": patient["access_token"]},
                           files={"file": ("x.png", PNG, "image/png")})
    url = up.json()["url"]

    assert (await client.get(url, headers=headers)).status_code == 200
    assert (await client.get(url, headers=other)).status_code == 404


async def test_doctor_upload_to_owned_and_foreign_patient(client: httpx.AsyncClient):
    headers = await _doctor(client)
    other = await _doctor(client, email="dr.outro@clinica.com")
    patient = await _patient(client, headers)

    ok = await client.post(f"/api/v1/patients/{patient['id']}/attachments", headers=headers,
                           files={"file": ("laudo.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert ok.status_code == 201

    forbidden = await client.post(f"/api/v1/patients/{patient['id']}/attachments", headers=other,
                                  files={"file": ("laudo.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert forbidden.status_code == 404


async def test_reject_disallowed_type(client: httpx.AsyncClient):
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    r = await client.post("/api/v1/patient/attachments",
                          headers={"X-Patient-Token": patient["access_token"]},
                          files={"file": ("virus.exe", b"MZ...", "application/x-msdownload")})
    assert r.status_code == 415


async def test_reject_oversize(client: httpx.AsyncClient, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.upload_max_bytes", 10)
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    r = await client.post("/api/v1/patient/attachments",
                          headers={"X-Patient-Token": patient["access_token"]},
                          files={"file": ("grande.png", PNG, "image/png")})
    assert r.status_code == 413


async def test_checkin_audio_is_transcribed_and_feeds_risk(client: httpx.AsyncClient, monkeypatch):
    async def _fake_transcribe(data: bytes, content_type: str, filename: str = "audio") -> str:
        return "não aguento mais, quero desistir de tudo"

    monkeypatch.setattr("app.services.checkin_service.transcribe", _fake_transcribe)
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}

    up = await client.post("/api/v1/patient/attachments", headers=ph,
                           files={"file": ("voz.m4a", b"fake-audio-bytes", "audio/mp4")})
    assert up.status_code == 201

    r = await client.post("/api/v1/patient/checkins", headers=ph,
                          json={"structured_responses": STABLE, "audio_url": up.json()["url"]})
    assert r.status_code == 201

    # o médico vê a transcrição no check-in
    checkins = (await client.get(f"/api/v1/patients/{patient['id']}/checkins",
                                 headers=headers)).json()
    assert len(checkins) == 1
    assert "desistir" in (checkins[0]["audio_transcript"] or "")
    # e a transcrição elevou o risco a ponto de gerar alerta
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    assert len(alerts) >= 1


async def test_checkin_without_transcription_keeps_audio_only(client: httpx.AsyncClient):
    # provider 'none' (default nos testes): áudio fica salvo, sem transcrição
    headers = await _doctor(client)
    patient = await _patient(client, headers)
    ph = {"X-Patient-Token": patient["access_token"]}
    up = await client.post("/api/v1/patient/attachments", headers=ph,
                           files={"file": ("voz.m4a", b"fake-audio-bytes", "audio/mp4")})
    r = await client.post("/api/v1/patient/checkins", headers=ph,
                          json={"structured_responses": STABLE, "audio_url": up.json()["url"]})
    assert r.status_code == 201
    checkins = (await client.get(f"/api/v1/patients/{patient['id']}/checkins",
                                 headers=headers)).json()
    assert checkins[0]["audio_transcript"] is None
    assert checkins[0]["audio_url"] == up.json()["url"]
