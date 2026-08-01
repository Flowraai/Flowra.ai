"""Provedores de push (plugáveis).

Contrato: `send(tokens, title, body) -> {token: "sent" | "failed: <motivo>"}`.

- `log` (default): registra em log — roda sem configuração (dev/testes).
- `expo`: Expo Push (RN/Expo), um único endpoint que entrega para FCM/APNs.

Para PWA (Web Push/VAPID) basta um novo provedor implementando o mesmo contrato.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger("flowra_care.push")

_EXPO_URL = "https://exp.host/--/api/v2/push/send"


class PushProvider(Protocol):
    async def send(self, tokens: list[str], title: str, body: str) -> dict[str, str]: ...


class LogPushProvider:
    async def send(self, tokens: list[str], title: str, body: str) -> dict[str, str]:
        results: dict[str, str] = {}
        for token in tokens:
            logger.info("[PUSH] %s | %s", token[:16], title)
            results[token] = "sent"
        return results


class ExpoPushProvider:
    async def send(self, tokens: list[str], title: str, body: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.expo_access_token:
            headers["Authorization"] = f"Bearer {settings.expo_access_token}"
        messages = [{"to": t, "title": title, "body": body} for t in tokens]
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(_EXPO_URL, headers=headers, json=messages)
            resp.raise_for_status()
            data = resp.json().get("data", [])
        results: dict[str, str] = {}
        for token, item in zip(tokens, data, strict=False):
            status = item.get("status", "unknown")
            results[token] = "sent" if status == "ok" else f"failed: {item.get('message', status)}"
        return results


def get_push_provider() -> PushProvider:
    if settings.push_provider == "expo":
        return ExpoPushProvider()
    return LogPushProvider()
