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


def _mask_target(target: str) -> str:
    """Mascara o contato (e-mail/telefone) para não vazar PII no log."""
    if "@" in target:
        local, _, domain = target.partition("@")
        return f"{local[:2]}***@{domain}"
    tail = target[-2:] if len(target) >= 2 else ""
    return f"***{tail}"


class Channel(Protocol):
    channel_type: NotificationChannel

    async def send(self, *, target: str, subject: str, body: str) -> None:
        """Entrega a notificação. Deve levantar exceção em caso de falha."""
        ...


class LogChannel:
    channel_type = NotificationChannel.LOG

    async def send(self, *, target: str, subject: str, body: str) -> None:
        # O contato é mascarado (PII); o subject já é minimizado (sem dado clínico).
        logger.warning("[NOTIFICAÇÃO] para=%s | %s", _mask_target(target), subject)


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


def _digits(target: str) -> str:
    return "".join(ch for ch in target if ch.isdigit())


class WhatsAppChannel:
    """WhatsApp. `target` é um telefone (E.164/dígitos). Dois provedores:

    - `meta` (default): API Cloud oficial. Fora da janela de 24h exige uma
      **template aprovada** (WHATSAPP_TEMPLATE_NAME).
    - `evolution`: Evolution API auto-hospedada (conecta por QR code, sem template).
      Reaproveita uma instância já existente (EVOLUTION_API_URL/KEY/INSTANCE).

    O conteúdo já vem **minimizado** (sem nome do paciente/dado clínico) — LGPD.
    """

    channel_type = NotificationChannel.WHATSAPP

    async def send(self, *, target: str, subject: str, body: str) -> None:
        if settings.whatsapp_provider.lower() == "evolution":
            await self._send_evolution(target, subject, body)
        else:
            await self._send_meta(target, subject, body)

    # ---- Evolution API (QR code) ----
    async def _send_evolution(self, target: str, subject: str, body: str) -> None:
        if not (settings.evolution_api_url and settings.evolution_api_key and settings.evolution_instance):
            raise RuntimeError(
                "Evolution API não configurada (defina EVOLUTION_API_URL, "
                "EVOLUTION_API_KEY e EVOLUTION_INSTANCE)."
            )
        text = f"{subject}\n\n{body}" if subject else body
        url = f"{settings.evolution_api_url.rstrip('/')}/message/sendText/{settings.evolution_instance}"
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                url,
                headers={"apikey": settings.evolution_api_key},
                json={"number": _digits(target), "text": text},
            )
            resp.raise_for_status()

    # ---- Meta Cloud API ----
    async def _send_meta(self, target: str, subject: str, body: str) -> None:
        if not (settings.whatsapp_phone_number_id and settings.whatsapp_access_token):
            raise RuntimeError(
                "WhatsApp não configurado (defina WHATSAPP_PHONE_NUMBER_ID e "
                "WHATSAPP_ACCESS_TOKEN)."
            )
        await self._post(self.build_payload(target, subject, body))

    @staticmethod
    def build_payload(target: str, subject: str, body: str) -> dict:
        to = "".join(ch for ch in target if ch.isdigit())
        if settings.whatsapp_template_name:
            return {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": settings.whatsapp_template_name,
                    "language": {"code": settings.whatsapp_template_lang},
                    "components": [
                        {"type": "body", "parameters": [{"type": "text", "text": body}]}
                    ],
                },
            }
        text = f"{subject}\n\n{body}" if subject else body
        return {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

    async def _post(self, payload: dict) -> None:
        url = (
            f"https://graph.facebook.com/{settings.whatsapp_api_version}"
            f"/{settings.whatsapp_phone_number_id}/messages"
        )
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                url,
                headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
                json=payload,
            )
            resp.raise_for_status()


_REGISTRY: dict[str, type[Channel]] = {
    NotificationChannel.LOG.value: LogChannel,
    NotificationChannel.EMAIL.value: EmailChannel,
    NotificationChannel.WEBHOOK.value: WebhookChannel,
    NotificationChannel.WHATSAPP.value: WhatsAppChannel,
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
