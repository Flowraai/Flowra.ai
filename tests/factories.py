"""Helpers de teste para inserir dados diretamente no banco (ex.: check-ins de
dias anteriores, respeitando a idempotência de um check-in por dia).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.db.session import AsyncSessionLocal
from app.models.checkin import CheckIn
from app.models.enums import RiskLevel


async def insert_checkin(
    patient_id: str | uuid.UUID,
    *,
    risk_level: RiskLevel = RiskLevel.GREEN,
    responses: dict | None = None,
    days_ago: int = 1,
) -> uuid.UUID:
    """Insere um check-in com data retroativa (simula check-in de outro dia)."""
    pid = patient_id if isinstance(patient_id, uuid.UUID) else uuid.UUID(patient_id)
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    async with AsyncSessionLocal() as session:
        checkin = CheckIn(
            patient_id=pid,
            structured_responses=responses or {},
            risk_level=risk_level,
            risk_reasons=[],
            category_risks={},
            created_at=when,
        )
        session.add(checkin)
        await session.commit()
        return checkin.id
