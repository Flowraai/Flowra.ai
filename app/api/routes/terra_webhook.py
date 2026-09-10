"""Webhook da Terra: recebe autorização e dados dos dispositivos dos pacientes.

Endpoint público (a Terra chama), autenticado pela ASSINATURA do payload
(header terra-signature, HMAC-SHA256 com o segredo do webhook). Sem o segredo
configurado, recusa — nunca aceita dado não verificado.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.patient import Patient
from app.services import wearable_service
from app.services.wearable_provider import map_terra_records

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger("flowra_care.wearable")

_DATA_EVENTS = {"daily", "sleep"}


def verify_signature(raw: bytes, header: str | None) -> bool:
    secret = settings.terra_signing_secret
    if not secret or not header:
        return False
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    t, v1 = parts.get("t"), parts.get("v1")
    if not t or not v1:
        return False
    expected = hmac.new(secret.encode(), f"{t}.{raw.decode()}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


@router.post("/webhooks/terra")
async def terra_webhook(request: Request, session: AsyncSession = Depends(get_db)) -> dict:
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("terra-signature")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="assinatura inválida")

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload inválido") from None

    event = (payload.get("type") or "").lower()
    user = payload.get("user") or {}
    user_id = user.get("user_id")
    reference_id = user.get("reference_id")

    # Autorização: liga o user_id da Terra ao nosso paciente (reference_id) e faz o
    # backfill inicial (pull dos últimos dias).
    if event in ("auth", "user_reauth") and reference_id and user_id:
        try:
            pid = uuid.UUID(str(reference_id))
        except ValueError:
            return {"ok": True}
        patient = await session.get(Patient, pid)
        if patient is None:
            return {"ok": True}
        conn = await wearable_service.get_connection(session, patient)
        if conn is None:
            conn, _ = await wearable_service.connect(session, patient)
        conn.provider = "terra"
        conn.external_user_id = str(user_id)
        await session.flush()
        await wearable_service.sync_patient(session, patient)
        return {"ok": True}

    # Desautorização: encerra a conexão.
    if event in ("deauth", "access_revoked", "google_no_datasource") and user_id:
        conn = await wearable_service.find_by_external(session, "terra", str(user_id))
        if conn is not None:
            conn.external_user_id = None
        return {"ok": True}

    # Dados (daily/sleep): grava direto do payload (sem nova chamada à API).
    if event in _DATA_EVENTS and user_id:
        conn = await wearable_service.find_by_external(session, "terra", str(user_id))
        if conn is None:
            return {"ok": True}
        patient = await session.get(Patient, conn.patient_id)
        if patient is None:
            return {"ok": True}
        records = payload.get("data") or []
        samples = (
            map_terra_records(records, [])
            if event == "daily"
            else map_terra_records([], records)
        )
        await wearable_service.upsert_samples(session, patient, "terra", list(samples.values()))
        return {"ok": True}

    return {"ok": True}
