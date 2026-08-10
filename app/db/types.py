"""Tipos de coluna customizados."""

from __future__ import annotations

import json
from typing import Any

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


class EncryptedJSON(TypeDecorator):
    """JSON (dict/list) cifrado em repouso (AES-256-GCM), transparente para o ORM.

    Serializa o valor em JSON e cifra na gravação; decifra e desserializa na
    leitura. Armazenado como Text. Sem ENCRYPTION_KEY, grava o JSON em claro (dev).
    Valores legados em claro — JSON puro, ex.: colunas migradas de JSONB — continuam
    legíveis (adoção gradual). NÃO use em colunas consultadas/filtradas/indexadas no
    banco: o conteúdo é opaco (cifrado e não-determinístico).
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: object) -> str | None:
        if value is None:
            return None
        return encrypt(json.dumps(value, ensure_ascii=False, separators=(",", ":")))

    def process_result_value(self, value: str | None, dialect: object) -> Any:
        if value is None:
            return None
        return json.loads(decrypt(value))
