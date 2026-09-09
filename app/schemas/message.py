"""Schemas de chat (mensagens)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MessageSender


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    # Anexos [{"url", "type"}] — o upload em si é um follow-up.
    attachments: list[dict] = Field(default_factory=list)
    # Só no envio do médico: entregar o TEXTO da mensagem no WhatsApp do paciente
    # (pelo número do médico, se conectado; senão pelos canais do servidor). Sem
    # isto, o paciente recebe só um aviso genérico ("abra o app"). Ignorado no
    # envio do paciente.
    deliver: bool = False


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender: MessageSender
    body: str
    attachments: list
    read_at: datetime | None = None
    created_at: datetime
    # Resultado da entrega no WhatsApp (só no retorno do envio manual do médico):
    # "whatsapp" | "no_contact" | "unavailable" | "not_connected" | "bad_number" | "failed".
    delivery: str | None = None
