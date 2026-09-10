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
from app.services.wearable_provider import DailySample, get_wearable_provider

DEFAULT_WINDOW = 14


async def find_by_external(
    session: AsyncSession, provider: str, external_user_id: str
) -> WearableConnection | None:
    """Localiza a conexão pelo id do usuário no fornecedor (usado nos webhooks)."""
    return await session.scalar(
        select(WearableConnection).where(
            WearableConnection.provider == provider,
            WearableConnection.external_user_id == external_user_id,
        )
    )


async def upsert_samples(
    session: AsyncSession, patient: Patient, provider: str, samples: list[DailySample]
) -> int:
    """Grava/atualiza os resumos diários (só sobrescreve métricas presentes na amostra)."""
    if not samples:
        return 0
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
            row = WearableDaily(
                patient_id=patient.id, tenant_id=patient.tenant_id, day=s.day, provider=provider,
            )
            session.add(row)
            existing[s.day] = row
        row.provider = provider
        # Só sobrescreve o que veio preenchido (webhooks parciais não zeram dados).
        if s.sleep_minutes is not None:
            row.sleep_minutes = s.sleep_minutes
        if s.resting_hr is not None:
            row.resting_hr = s.resting_hr
        if s.hrv_ms is not None:
            row.hrv_ms = s.hrv_ms
        if s.steps is not None:
            row.steps = s.steps
    await session.flush()
    return len(samples)


async def get_connection(session: AsyncSession, patient: Patient) -> WearableConnection | None:
    return await session.scalar(
        select(WearableConnection).where(WearableConnection.patient_id == patient.id)
    )


async def get_connection_by_patient_id(session: AsyncSession, patient_id) -> WearableConnection | None:
    return await session.scalar(
        select(WearableConnection).where(WearableConnection.patient_id == patient_id)
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


async def ensure_connection(
    session: AsyncSession, patient: Patient, provider: str
) -> WearableConnection:
    """Garante uma conexão para o paciente (usada pelo app de celular, sem OAuth)."""
    conn = await get_connection(session, patient)
    if conn is None:
        conn = WearableConnection(
            patient_id=patient.id,
            tenant_id=patient.tenant_id,
            provider=provider,
            connected_at=datetime.now(timezone.utc),
        )
        session.add(conn)
        await session.flush()
    return conn


async def sync_patient(
    session: AsyncSession, patient: Patient, days: int = DEFAULT_WINDOW
) -> int:
    """Sincroniza o resumo diário (upsert por dia). Retorna quantos dias gravados."""
    conn = await get_connection(session, patient)
    if conn is None:
        return 0
    provider = get_wearable_provider(conn.provider)
    samples = await provider.sync(patient, conn, days)
    n = await upsert_samples(session, patient, conn.provider, samples)
    conn.last_sync_at = datetime.now(timezone.utc)
    await session.flush()
    return n


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
