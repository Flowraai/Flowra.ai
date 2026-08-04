"""LGPD — minimização de dados: o que sai para canais externos/push e o que
fica retido em auditoria não pode conter dado clínico ou identificar o paciente.
"""

from __future__ import annotations

import httpx
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.enums import AlertUrgency, AuditAction, RiskLevel
from app.services.notifications import _render

CRITICAL = {
    "mood": 1, "anxiety": 9, "slept_well": "nao", "sleep_hours": 2,
    "medication_taken": "nao", "crisis": "sim", "side_effects": "sim",
}


# ---------- Conteúdo enviado a canais externos / push ----------
def test_external_notification_has_no_pii_or_clinical_detail():
    alert = Alert(
        level=RiskLevel.RED, urgency=AlertUrgency.IMMEDIATE,
        reason="sinal crítico no texto livre: 'me matar'",
        reasons_detail=["sinal crítico no texto livre: 'me matar'"],
    )
    subject, body = _render(alert)
    blob = f"{subject}\n{body}".lower()

    # não vaza motivo clínico nem o texto/relato do paciente
    assert "me matar" not in blob
    assert "texto livre" not in blob
    assert "motivo" not in blob
    # não vaza o nível de risco bruto (green/yellow/orange/red)
    assert "red" not in blob
    # sinaliza urgência e direciona ao painel (onde o detalhe fica sob login)
    assert "urgente" in blob and "painel" in blob


def test_external_notification_routine_variant_is_also_minimal():
    alert = Alert(
        level=RiskLevel.ORANGE, urgency=AlertUrgency.ROUTINE,
        reason="humor muito baixo", reasons_detail=["humor muito baixo"],
    )
    subject, body = _render(alert)
    blob = f"{subject}\n{body}".lower()
    assert "humor" not in blob
    assert "painel" in blob


# ---------- Auditoria retida após eliminação ----------
async def _register(client: httpx.AsyncClient) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "email": "dra.ana@clinica.com", "password": "senhaforte123", "name": "Dra. Ana"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_audit_does_not_retain_free_text_signals(client: httpx.AsyncClient):
    headers = await _register(client)
    patient = (await client.post("/api/v1/patients", headers=headers,
                                 json={"name": "João", "consent_given": True})).json()
    # texto livre com sinal crítico — não pode acabar retido na auditoria
    await client.post("/api/v1/patient/checkins",
                      headers={"X-Patient-Token": patient["access_token"]},
                      json={"structured_responses": CRITICAL,
                            "free_text": "não aguento mais, quero me matar"})

    async with AsyncSessionLocal() as session:
        logs = list((await session.execute(
            select(AuditLog).where(AuditLog.action == AuditAction.RISK_CALCULATED)
        )).scalars().all())

    assert logs, "deveria haver ao menos um log de cálculo de risco"
    for log in logs:
        serialized = str(log.metadata_).lower()
        assert "me matar" not in serialized
        assert "texto livre" not in serialized
        assert "reasons" not in serialized
        # os níveis (não-textuais) continuam presentes para auditar o cálculo
        assert "combined_level" in serialized
