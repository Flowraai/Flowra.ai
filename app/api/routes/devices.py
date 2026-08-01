"""Registro de device tokens (push) do médico."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import DeviceOwnerType
from app.schemas.device import DeviceRegister, DeviceTokenRead
from app.services.push_service import register_device, unregister_device

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DeviceTokenRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: DeviceRegister,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> DeviceTokenRead:
    device = await register_device(
        session, owner_type=DeviceOwnerType.DOCTOR, owner_id=doctor.id,
        token=payload.token, platform=payload.platform,
    )
    return DeviceTokenRead.model_validate(device)


@router.post("/unregister", status_code=status.HTTP_204_NO_CONTENT)
async def unregister(
    payload: DeviceRegister,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> None:
    await unregister_device(session, payload.token)
