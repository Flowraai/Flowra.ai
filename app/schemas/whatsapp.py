"""Schemas do WhatsApp por médico (Evolution API)."""

from __future__ import annotations

from pydantic import BaseModel


class WhatsAppStatus(BaseModel):
    connected: bool
    state: str  # open | connecting | close | disconnected | notfound | unknown


class WhatsAppConnect(BaseModel):
    state: str | None = None
    qr: str | None = None           # data-URI (imagem base64) para exibir e escanear
    pairing_code: str | None = None  # alternativa ao QR (digitar no celular)
