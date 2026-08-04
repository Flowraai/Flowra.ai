"""Anexos: upload (paciente e médico) e download com controle de acesso.

Os bytes vão para o backend de armazenamento; os metadados para a tabela
`attachments`. O download é liberado apenas para o paciente dono do anexo ou
para o médico responsável por ele (LGPD — arquivos clínicos são sensíveis).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor, get_current_patient
from app.core.security import decode_access_token, hash_patient_token
from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.attachment import AttachmentRead
from app.services.attachment_service import load_bytes, store_attachment, validate_upload

router = APIRouter(tags=["attachments"])

_bearer = HTTPBearer(auto_error=False)
_patient_token_header = APIKeyHeader(name="X-Patient-Token", auto_error=False)


async def _read_validated(file: UploadFile) -> tuple[bytes, str]:
    data = await file.read()
    ctype = validate_upload(file.content_type, len(data))
    return data, ctype


@router.post(
    "/patient/attachments", response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED, tags=["patient-app"],
)
async def upload_patient_attachment(
    file: UploadFile = File(...),
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> Attachment:
    """Paciente envia uma foto/arquivo/áudio (referenciável em mensagem ou check-in)."""
    data, ctype = await _read_validated(file)
    return await store_attachment(
        session, tenant_id=patient.tenant_id, patient_id=patient.id,
        uploaded_by=f"patient:{patient.id}", data=data, content_type=ctype,
        filename=file.filename,
    )


@router.post(
    "/patients/{patient_id}/attachments", response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_doctor_attachment(
    patient_id: uuid.UUID,
    file: UploadFile = File(...),
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Attachment:
    """Médico anexa um arquivo ao contexto de um paciente que ele acompanha."""
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    data, ctype = await _read_validated(file)
    return await store_attachment(
        session, tenant_id=patient.tenant_id, patient_id=patient.id,
        uploaded_by=f"doctor:{doctor.id}", data=data, content_type=ctype,
        filename=file.filename,
    )


async def _authorize(
    session: AsyncSession, attachment: Attachment,
    patient_token: str | None, credentials: HTTPAuthorizationCredentials | None,
) -> bool:
    """Libera se o requisitante é o paciente dono ou o médico responsável."""
    if patient_token:
        result = await session.execute(
            select(Patient).where(Patient.access_token_hash == hash_patient_token(patient_token))
        )
        patient = result.scalar_one_or_none()
        if patient is not None and patient.is_active and patient.id == attachment.patient_id:
            return True
    if credentials:
        payload = decode_access_token(credentials.credentials)
        if payload and payload.get("type") == "access":
            try:
                user_id = uuid.UUID(str(payload.get("sub")))
            except (ValueError, TypeError):
                return False
            user = await session.get(User, user_id)
            if user is None or not user.is_active:
                return False
            result = await session.execute(select(Doctor).where(Doctor.user_id == user.id))
            doctor = result.scalar_one_or_none()
            patient = await session.get(Patient, attachment.patient_id)
            if doctor is not None and patient is not None and patient.doctor_id == doctor.id:
                return True
    return False


@router.get("/attachments/{attachment_id}")
async def download_attachment(
    attachment_id: uuid.UUID,
    patient_token: str | None = Depends(_patient_token_header),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> Response:
    attachment = await session.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anexo não encontrado.")
    if not await _authorize(session, attachment, patient_token, credentials):
        # 404 (não 403) para não revelar a existência do anexo a quem não tem acesso.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anexo não encontrado.")
    data = load_bytes(attachment)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conteúdo indisponível.")
    disposition = "inline"
    if attachment.filename:
        disposition = f'inline; filename="{attachment.filename}"'
    return Response(
        content=data, media_type=attachment.content_type,
        headers={"Content-Disposition": disposition},
    )
