"""Tipos de coluna customizados."""

from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.crypto import decrypt, encrypt


class EncryptedText(TypeDecorator):
    """Texto cifrado em repouso (AES-256-GCM) de forma transparente.

    Armazena como Text; cifra na gravação e decifra na leitura. Sem
    ENCRYPTION_KEY, comporta-se como Text comum (dev). Não use em colunas usadas
    em filtros/ordenções no banco — a cifragem é não-determinística.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        return encrypt(value) if value is not None else None

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        return decrypt(value) if value is not None else None
