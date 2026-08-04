"""Armazenamento de anexos (fotos/arquivos/áudio), plugável.

O contrato é `StorageBackend`. O padrão do MVP é o `LocalStorageBackend` (grava
em disco sob `STORAGE_DIR`). Em produção, troca-se por um backend de object
storage (S3/GCS/Azure) implementando o mesmo protocolo — os metadados (tipo,
tamanho, dono) ficam na tabela `attachments`, então o backend guarda só os bytes.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import settings


class StorageBackend(Protocol):
    def save(self, data: bytes) -> str:
        """Grava os bytes e devolve a chave de armazenamento (opaca)."""
        ...

    def load(self, key: str) -> bytes | None:
        """Lê os bytes pela chave; None se não existir."""
        ...

    def delete(self, key: str) -> None:
        ...


class LocalStorageBackend:
    """Grava cada anexo como um arquivo sob `base_dir`, nomeado por uma chave
    aleatória (uuid4). Sem extensão: o tipo vive na tabela `attachments`."""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes) -> str:
        key = uuid.uuid4().hex
        (self._base / key).write_bytes(data)
        return key

    def load(self, key: str) -> bytes | None:
        path = self._base / key
        if not path.is_file():
            return None
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._base / key
        if path.is_file():
            path.unlink()


def get_storage_backend() -> StorageBackend:
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalStorageBackend(settings.storage_dir)
    raise ValueError(
        f"STORAGE_BACKEND desconhecido: {settings.storage_backend!r} "
        "(suportado no MVP: 'local'; produção implementa object storage)."
    )
