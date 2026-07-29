"""Serviço de auditoria — registra ações sensíveis (compliance, seção 9)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import AuditAction


async def record(
    session: AsyncSession,
    *,
    action: AuditAction,
    actor: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Cria uma entrada de auditoria. Não faz commit (fica a cargo do chamador)."""
    log = AuditLog(
        action=action,
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_=metadata or {},
    )
    session.add(log)
    return log
