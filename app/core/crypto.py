"""Criptografia simétrica dos campos sensíveis (criptografia em repouso).

AES-256-GCM (autenticado) com chave de 32 bytes vinda de `ENCRYPTION_KEY`
(base64). Sem chave configurada, os valores passam em claro — modo de
desenvolvimento. Valores já em claro no banco (legado/dev) são lidos como estão;
só o que tem o prefixo `enc:v1:` é decifrado. Assim a adoção da chave é gradual e
não quebra dados existentes.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_PREFIX = "enc:v1:"
_NONCE_BYTES = 12


def _key() -> bytes | None:
    if not settings.encryption_key:
        return None
    try:
        key = base64.b64decode(settings.encryption_key)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("ENCRYPTION_KEY inválida: use base64 de 32 bytes.") from exc
    if len(key) != 32:
        raise ValueError("ENCRYPTION_KEY deve decodificar para 32 bytes (AES-256).")
    return key


def encryption_enabled() -> bool:
    return _key() is not None


def encrypt(plaintext: str) -> str:
    """Cifra o texto; se não houver chave, devolve em claro (dev)."""
    key = _key()
    if key is None:
        return plaintext
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return _PREFIX + base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(value: str) -> str:
    """Decifra um valor com prefixo `enc:v1:`; devolve o resto como está (legado/dev)."""
    if not value.startswith(_PREFIX):
        return value
    key = _key()
    if key is None:
        raise ValueError(
            "Há dados cifrados no banco, mas ENCRYPTION_KEY não está configurada."
        )
    raw = base64.b64decode(value[len(_PREFIX):])
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")
