"""Device tokens para push. Polimórfico: o dono é um paciente ou um médico.

Provider-agnóstico: `token` guarda o identificador do dispositivo no provedor
(Expo push token, FCM token ou subscription Web Push serializada) e `platform`
indica ios/android/web.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import DeviceOwnerType


class DeviceToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "device_tokens"

    owner_type: Mapped[DeviceOwnerType] = mapped_column(
        Enum(DeviceOwnerType, name="device_owner_type"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), index=True, nullable=False)
    token: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # ios | android | web
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
