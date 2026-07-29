"""Canais de notificação plugáveis. Contrato: `Channel.send(target, subject, body)`.

O default (`log`) sempre funciona e roda sem configuração. `email` (SMTP) e
`webhook` (ponte para WhatsApp/push) ativam-se via variáveis de ambiente.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.core.config import settings
from app.models.enums import NotificationChannel

logger = logging.getLogger("flowra_care.notifications")


class Channel(Protocol):
    channel_type: NotificationChannel

    async def send(self, *, target: str, subject: str, body: str) -> None:
        """Entrega a notificação. Deve levantar exceção em caso de falha."""
        ...


class LogChannel:
    channel_type = NotificationChannel.LOG

    async def send(self, *, target: str, subject: str, body: str) -> None:
        logger.warning("[NOTIFICAÇÃO] para=%s | %s", target, subject)


class EmailChannel:
    channel_type = NotificationChannel.EMAIL

    async def send(self, *, target: str, subject: str, body: str) -> None:
        if not settings.smtp_host or not settings.smtp_from:
            raise RuntimeError("SMTP não configurado (defina SMTP_HOST e SMTP_FROM).")
        # smtplib é síncrono: roda numa thread para não bloquear o event loop.
        await asyncio.to_thread(self._send_sync, target, subject, body)

    @staticmethod
    def _send_sync(target: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = target
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)


class WebhookChannel:
    channel_type = NotificationChannel.WEBHOOK

    async def send(self, *, target: str, subject: str, body: str) -> None:
        if not settings.notification_webhook_url:
            raise RuntimeError("Webhook não configurado (defina NOTIFICATION_WEBHOOK_URL).")
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                settings.notification_webhook_url,
                json={"target": target, "subject": subject, "body": body},
            )
            resp.raise_for_status()


_REGISTRY: dict[str, type[Channel]] = {
    NotificationChannel.LOG.value: LogChannel,
    NotificationChannel.EMAIL.value: EmailChannel,
    NotificationChannel.WEBHOOK.value: WebhookChannel,
}


def get_active_channels() -> list[Channel]:
    """Instancia os canais configurados em NOTIFICATION_CHANNELS (ignora inválidos)."""
    channels: list[Channel] = []
    for name in settings.notification_channels:
        impl = _REGISTRY.get(name.strip().lower())
        if impl is None:
            logger.warning("Canal de notificação desconhecido ignorado: %s", name)
            continue
        channels.append(impl())
    if not channels:  # nunca fica em silêncio: log como fallback seguro
        channels.append(LogChannel())
    return channels
