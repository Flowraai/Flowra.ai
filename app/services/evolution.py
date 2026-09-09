"""Cliente da Evolution API (WhatsApp por QR), com instância **por médico**.

Uma única Evolution API (auto-hospedada, EVOLUTION_API_URL/KEY) hospeda várias
instâncias — uma por médico. Cada médico pareia o próprio número por QR; as
mensagens aos pacientes dele saem do número dele.

Contrato mínimo: criar/conectar (QR)/estado/desconectar a instância e enviar texto.
Defensivo quanto ao formato de resposta (varia entre versões da Evolution).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("flowra_care.evolution")


def configured() -> bool:
    return bool(settings.evolution_api_url and settings.evolution_api_key)


def instance_name_for(doctor_id: uuid.UUID) -> str:
    """Nome estável e único da instância do médico."""
    return f"care_{doctor_id.hex[:16]}"


def normalize_msisdn(number: str) -> str:
    """Normaliza um telefone para o formato que o WhatsApp espera (só dígitos, com DDI).

    Aceita como o médico costuma digitar no Brasil e completa o DDI 55 quando falta:
      "(43) 98858-0825" / "43988580825"  -> "5543988580825"
      "+55 43 98858-0825" / "5543988580825" -> "5543988580825"
    Números que já tenham DDI (>= 12 dígitos) ou de outros países são mantidos.
    """
    digits = "".join(ch for ch in number if ch.isdigit())
    if not digits:
        return digits
    if digits.startswith("55") and len(digits) >= 12:
        return digits  # já tem DDI Brasil
    if len(digits) in (10, 11):  # DDD + fixo(10)/celular(11), sem DDI
        return "55" + digits
    return digits  # já internacional ou formato incomum — não mexe


def looks_deliverable(number: str) -> bool:
    """Um número só é enviável se, após normalizar, tiver DDI+DDD+assinante (>= 12)."""
    return len(normalize_msisdn(number)) >= 12


def _base() -> str:
    return settings.evolution_api_url.rstrip("/")  # type: ignore[union-attr]


def _headers() -> dict[str, str]:
    return {"apikey": settings.evolution_api_key or "", "Content-Type": "application/json"}


async def _request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20, headers=_headers()) as http:
        resp = await http.request(method, f"{_base()}{path}", **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}


async def ensure_instance(name: str) -> None:
    """Cria a instância se ainda não existir (idempotente)."""
    try:
        await _request(
            "POST",
            "/instance/create",
            json={"instanceName": name, "integration": "WHATSAPP-BAILEYS", "qrcode": True},
        )
    except httpx.HTTPStatusError as exc:
        # 403/409 costuma significar "já existe" — seguimos.
        if exc.response.status_code not in (400, 401, 403, 409):
            raise


async def connect(name: str) -> dict[str, Any]:
    """Inicia o pareamento e retorna o QR (quando ainda não conectado).

    Devolve {"state": ..., "qr": <data-uri base64 ou None>, "pairing_code": <str|None>}.
    """
    data = await _request("GET", f"/instance/connect/{name}")
    qr = data.get("base64") or (data.get("qrcode") or {}).get("base64")
    if qr and not str(qr).startswith("data:"):
        qr = f"data:image/png;base64,{qr}"
    pairing = data.get("pairingCode") or (data.get("qrcode") or {}).get("pairingCode")
    return {"state": data.get("state") or data.get("instance", {}).get("state"), "qr": qr, "pairing_code": pairing}


async def state(name: str) -> str:
    """Estado da conexão: 'open' (conectado) | 'connecting' | 'close' | 'unknown'."""
    try:
        data = await _request("GET", f"/instance/connectionState/{name}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return "notfound"
        raise
    inst = data.get("instance") or data
    return inst.get("state") or "unknown"


async def disconnect(name: str) -> None:
    """Desloga e remove a instância (idempotente)."""
    for path in (f"/instance/logout/{name}", f"/instance/delete/{name}"):
        try:
            await _request("DELETE", path)
        except httpx.HTTPStatusError:
            pass  # já deslogado/removido


async def send_text(name: str, number: str, text: str) -> None:
    """Envia texto pela instância `name` para `number` (normaliza DDI+DDD)."""
    await _request(
        "POST", f"/message/sendText/{name}", json={"number": normalize_msisdn(number), "text": text}
    )
