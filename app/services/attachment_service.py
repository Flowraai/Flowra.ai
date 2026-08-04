"""Serviço de anexos: validação, gravação no storage e persistência dos metadados."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.attachment import Attachment
from app.services.storage import get_storage_backend

_URL_PREFIX = "/api/v1/attachments/"


def validate_upload(content_type: str | None, size: int) -> str:
    """Valida tipo e tamanho; devolve o content_type normalizado ou levanta 4xx."""
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in settings.upload_allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de arquivo não permitido: {ctype or 'desconhecido'}.",
        )
    if size <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")
    if size > settings.upload_max_bytes:
        raise HTTPException(
            status_code=413,  # Content Too Large
            detail=f"Arquivo excede o limite de {settings.upload_max_bytes} bytes.",
        )
    return ctype


async def store_attachment(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    patient_id: uuid.UUID,
    uploaded_by: str,
    data: bytes,
    content_type: str,
    filename: str | None,
) -> Attachment:
    key = get_storage_backend().save(data)
    attachment = Attachment(
        tenant_id=tenant_id, patient_id=patient_id, uploaded_by=uploaded_by,
        storage_key=key, content_type=content_type, size_bytes=len(data),
        filename=filename,
    )
    session.add(attachment)
    await session.flush()
    return attachment


def attachment_id_from_ref(ref: str | None) -> uuid.UUID | None:
    """Extrai o id de um anexo a partir da URL (/api/v1/attachments/<id>) ou do id puro."""
    if not ref:
        return None
    candidate = ref[len(_URL_PREFIX):] if ref.startswith(_URL_PREFIX) else ref
    try:
        return uuid.UUID(candidate)
    except (ValueError, TypeError):
        return None


def load_bytes(attachment: Attachment) -> bytes | None:
    return get_storage_backend().load(attachment.storage_key)
