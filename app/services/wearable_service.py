"""Conexão e ingestão de dados de vestíveis (relógio/pulseira).

Guarda um resumo DIÁRIO por paciente (upsert por dia). Agnóstico de fornecedor —
delega a coleta ao `wearable_provider` configurado. O `demo` já preenche dados de
exemplo para o fluxo funcionar de ponta a ponta.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.patient import Patient
from app.models.wearable import WearableConnection, WearableDaily
from app.services.wearable_provider import get_wearable_provider

DEFAULT_WINDOW = 14


async def get_connection(session: AsyncSession, patient: Patient) -> WearableConnection | None:
    return await session.scalar(
        select(WearableConnection).where(WearableConnection.patient_id == patient.id)
    )


async def connect(session: AsyncSession, patient: Patient) -> tuple[WearableConnection, str | None]:
    """Cria (ou reusa) a conexão. Retorna (conexão, url_oauth|None).

    Provedores instantâneos (demo) já fazem uma primeira sincronização.
    """
    provider_slug = (settings.wearable_provider or "demo").lower()
    conn = await get_connection(session, patient)
    if conn is None:
        conn = WearableConnection(
            patient_id=patient.id,
            tenant_id=patient.tenant_id,
            provider=provider_slug,
            connected_at=datetime.now(timezone.utc),
        )
        session.add(conn)
        await session.flush()

    provider = get_wearable_provider(provider_slug)
    oauth_url = await provider.begin_connect(patient, conn)
    if oauth_url is None:
        await sync_patient(session, patient, DEFAULT_WINDOW)
    return conn, oauth_url


async def sync_patient(
    session: AsyncSession, patient: Patient, days: int = DEFAULT_WINDOW
) -> int:
    """Sincroniza o resumo diário (upsert por dia). Retorna quantos dias gravados."""
    conn = await get_connection(session, patient)
    if conn is None:
        return 0
    provider = get_wearable_provider(conn.provider)
    samples = await provider.sync(patient, conn, days)

    existing = {
        r.day: r
        for r in (
            await session.execute(
                select(WearableDaily).where(WearableDaily.patient_id == patient.id)
            )
        )
        .scalars()
        .all()
    }
    for s in samples:
        row = existing.get(s.day)
        if row is None:
            session.add(
                WearableDaily(
                    patient_id=patient.id,
                    tenant_id=patient.tenant_id,
                    day=s.day,
                    provider=conn.provider,
                    sleep_minutes=s.sleep_minutes,
                    resting_hr=s.resting_hr,
                    hrv_ms=s.hrv_ms,
                    steps=s.steps,
                )
            )
        else:
            row.provider = conn.provider
            row.sleep_minutes = s.sleep_minutes
            row.resting_hr = s.resting_hr
            row.hrv_ms = s.hrv_ms
            row.steps = s.steps
    conn.last_sync_at = datetime.now(timezone.utc)
    await session.flush()
    return len(samples)


async def disconnect(session: AsyncSession, patient: Patient) -> None:
    """Remove a conexão (mantém o histórico diário já coletado)."""
    await session.execute(
        delete(WearableConnection).where(WearableConnection.patient_id == patient.id)
    )


async def recent_daily(
    session: AsyncSession, patient: Patient, days: int = DEFAULT_WINDOW
) -> list[WearableDaily]:
    rows = list(
        (
            await session.execute(
                select(WearableDaily)
                .where(WearableDaily.patient_id == patient.id)
                .order_by(WearableDaily.day.desc())
                .limit(days)
            )
        )
        .scalars()
        .all()
    )
    return rows


def _avg(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


async def summary(session: AsyncSession, patient: Patient, days: int = DEFAULT_WINDOW) -> dict:
    """Resumo para painel/app: conectado?, última leitura e médias da janela."""
    conn = await get_connection(session, patient)
    rows = await recent_daily(session, patient, days)  # desc (mais recente primeiro)
    latest = rows[0] if rows else None

    def col(attr: str) -> list[int]:
        return [v for v in (getattr(r, attr) for r in rows) if v is not None]

    return {
        "connected": conn is not None,
        "provider": conn.provider if conn else None,
        "last_sync_at": conn.last_sync_at if conn else None,
        "latest": latest,
        "avg_sleep_minutes": _avg(col("sleep_minutes")),
        "avg_resting_hr": _avg(col("resting_hr")),
        "avg_hrv_ms": _avg(col("hrv_ms")),
        "avg_steps": _avg(col("steps")),
        "days": list(reversed(rows)),  # asc para o gráfico
    }
