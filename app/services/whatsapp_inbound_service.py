"""Confirmação de mão dupla: interpreta as respostas do paciente no WhatsApp.

A Evolution API entrega as mensagens recebidas no webhook; aqui a gente:
  1. extrai (instância, número, texto) do payload (formato varia entre versões);
  2. acha o médico pela instância e o paciente pelo número;
  3. lê a intenção (confirmar / remarcar) e atualiza a próxima consulta aberta;
  4. responde uma confirmação curta pelo mesmo WhatsApp.

Tudo best-effort: mensagem que não casa com nada é ignorada em silêncio.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.services import evolution

logger = logging.getLogger("flowra_care.whatsapp_inbound")

_OPEN = (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)

_YES = {"sim", "s", "confirmo", "confirmado", "confirmada", "ok", "okay", "isso",
        "pode", "positivo", "confirmar", "1", "👍", "👍🏻", "👍🏽"}
_RESCHEDULE = {"remarcar", "remarca", "nao", "não", "n", "mudar", "trocar", "outro", "2"}


@dataclass
class InboundMessage:
    instance: str
    number: str      # só dígitos (com DDI)
    text: str


def _digits(jid_or_number: str) -> str:
    raw = jid_or_number.split("@", 1)[0]          # tira o sufixo @s.whatsapp.net
    raw = raw.split(":", 1)[0]                     # tira o sufixo de device (:12)
    return "".join(ch for ch in raw if ch.isdigit())


def parse_event(payload: dict[str, Any]) -> InboundMessage | None:
    """Extrai a mensagem de texto recebida do payload da Evolution (defensivo)."""
    instance = payload.get("instance") or payload.get("instanceName")
    data = payload.get("data")
    if isinstance(data, list):
        data = data[0] if data else None
    if not instance or not isinstance(data, dict):
        return None

    key = data.get("key") or {}
    if key.get("fromMe"):
        return None                               # eco da nossa própria mensagem
    jid = key.get("remoteJid") or ""
    if jid.endswith("@g.us"):
        return None                               # ignora grupos

    message = data.get("message") or {}
    text = (
        message.get("conversation")
        or (message.get("extendedTextMessage") or {}).get("text")
        or ""
    )
    number = _digits(jid)
    if not number or not str(text).strip():
        return None
    return InboundMessage(instance=str(instance), number=number, text=str(text).strip())


def _tokens(text: str) -> set[str]:
    """Palavras normalizadas (minúsculas, sem acento, sem pontuação) da mensagem."""
    lowered = text.strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_txt = "".join(c for c in decomposed if not unicodedata.combining(c))
    return {w.strip(".,!?;:") for w in ascii_txt.split()}


def interpret(text: str) -> str | None:
    """'confirm' | 'reschedule' | None conforme a resposta do paciente.

    Olha todas as palavras. Remarcar/negar têm prioridade sobre confirmar (ex.:
    "não confirmo" e "sim, mas preciso remarcar" caem como remarcação).
    """
    toks = _tokens(text)
    if toks & _RESCHEDULE:
        return "reschedule"
    if (toks & _YES) or "👍" in text:
        return "confirm"
    return None


async def _match_appointment(
    session: AsyncSession, doctor: Doctor, number: str
) -> tuple[Patient, Appointment] | None:
    """Acha o paciente do médico pelo número e a próxima consulta aberta dele."""
    target = evolution.normalize_msisdn(number)
    patients = list(
        (await session.execute(select(Patient).where(Patient.doctor_id == doctor.id)))
        .scalars()
        .all()
    )
    patient = next(
        (p for p in patients if p.contact and evolution.normalize_msisdn(p.contact) == target),
        None,
    )
    if patient is None:
        return None
    appt = (
        await session.execute(
            select(Appointment)
            .where(
                Appointment.patient_id == patient.id,
                Appointment.status.in_(_OPEN),
                Appointment.scheduled_at >= datetime.now(timezone.utc),
            )
            .order_by(Appointment.scheduled_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if appt is None:
        return None
    return patient, appt


async def handle_inbound(session: AsyncSession, msg: InboundMessage) -> str | None:
    """Processa a resposta e atualiza a consulta. Retorna a ação aplicada ou None."""
    intent = interpret(msg.text)
    if intent is None:
        return None

    doctor = (
        await session.execute(select(Doctor).where(Doctor.whatsapp_instance == msg.instance))
    ).scalar_one_or_none()
    if doctor is None:
        return None

    match = await _match_appointment(session, doctor, msg.number)
    if match is None:
        return None
    _patient, appt = match

    if intent == "confirm":
        appt.status = AppointmentStatus.CONFIRMED
        reply = "✅ Presença confirmada! Até lá."
        action = "confirmed"
    else:  # reschedule
        appt.reschedule_requested_at = datetime.now(timezone.utc)
        appt.reschedule_note = msg.text[:500]
        reply = "Ok! Vou avisar para remarcar e retornamos com um novo horário."
        action = "reschedule_requested"

    # Responde pelo mesmo WhatsApp (best-effort — não falha o webhook).
    try:
        await evolution.send_text(msg.instance, msg.number, reply)
    except Exception:  # noqa: BLE001
        logger.warning("Falha ao responder a confirmação no WhatsApp (seguindo)")
    return action
