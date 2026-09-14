"""Gera o payload PIX "copia e cola" (BR Code EMV) — estático, sem gateway.

O médico configura a chave PIX e a cidade; cada cobrança particular vira um
código que o paciente cola no app do banco. A conciliação continua manual (o
médico marca "recebido"): não há webhook nem PSP no meio.

Formato EMV®/BR Code do BACEN. O CRC16 (CCITT-FALSE) é validado no teste contra o
valor de referência conhecido (0x29B1 para "123456789").
"""

from __future__ import annotations

import re
import unicodedata


def _ascii(text: str) -> str:
    """Remove acentos e caracteres não-ASCII (campos EMV são ASCII)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c) and ord(c) < 128)


def _field(id_: str, value: str) -> str:
    return f"{id_}{len(value):02d}{value}"


def crc16(payload: str) -> str:
    """CRC-16/CCITT-FALSE (init 0xFFFF, poly 0x1021), 4 hex maiúsculos."""
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def build_pix_payload(
    key: str, receiver_name: str, city: str, amount_cents: int, txid: str = "***"
) -> str:
    """Monta o BR Code estático com valor. `key` é a chave PIX do recebedor."""
    name = (_ascii(receiver_name).strip() or "RECEBEDOR")[:25]
    town = (_ascii(city).strip() or "CIDADE")[:15]
    clean_txid = re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "***"
    amount = f"{amount_cents / 100:.2f}"

    merchant_account = _field("00", "br.gov.bcb.pix") + _field("01", key.strip())
    payload = (
        _field("00", "01")                      # Payload Format Indicator
        + _field("26", merchant_account)        # Merchant Account Information (PIX)
        + _field("52", "0000")                  # Merchant Category Code
        + _field("53", "986")                   # Moeda (BRL)
        + _field("54", amount)                  # Valor
        + _field("58", "BR")                    # País
        + _field("59", name)                    # Nome do recebedor
        + _field("60", town)                    # Cidade
        + _field("62", _field("05", clean_txid))  # Dados adicionais (txid)
        + "6304"                                # CRC (id + tamanho), valor a seguir
    )
    return payload + crc16(payload)
