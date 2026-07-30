"""Enumerações do domínio do Flowra Care."""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    """Perfis com conta de acesso via senha/JWT. Pacientes usam token opaco."""

    DOCTOR = "doctor"
    ADMIN = "admin"


class RiskLevel(str, enum.Enum):
    """Índice de risco do paciente (🟢🟡🟠🔴)."""

    GREEN = "green"    # 🟢 Estável — dentro do esperado
    YELLOW = "yellow"  # 🟡 Atenção — pequenas variações
    ORANGE = "orange"  # 🟠 Acompanhamento necessário — padrão de piora
    RED = "red"        # 🔴 Alta prioridade — sinal de risco relevante

    @property
    def order(self) -> int:
        return _RISK_ORDER[self]

    @property
    def emoji(self) -> str:
        return _RISK_EMOJI[self]

    def escalate(self, other: "RiskLevel") -> "RiskLevel":
        """Combinação conservadora: mantém sempre o maior risco."""
        return self if self.order >= other.order else other


_RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.GREEN: 0,
    RiskLevel.YELLOW: 1,
    RiskLevel.ORANGE: 2,
    RiskLevel.RED: 3,
}

_RISK_EMOJI: dict[RiskLevel, str] = {
    RiskLevel.GREEN: "🟢",
    RiskLevel.YELLOW: "🟡",
    RiskLevel.ORANGE: "🟠",
    RiskLevel.RED: "🔴",
}


class AlertUrgency(str, enum.Enum):
    ROUTINE = "routine"      # 🟠 notificar médico (não urgente)
    IMMEDIATE = "immediate"  # 🔴 alertar médico imediatamente


class AlertStatus(str, enum.Enum):
    PENDING = "pending"            # gerado, ainda não entregue
    NOTIFIED = "notified"          # médico notificado
    ACKNOWLEDGED = "acknowledged"  # médico visualizou/assumiu
    RESOLVED = "resolved"          # tratado/encerrado


class QuestionType(str, enum.Enum):
    SCALE = "scale"          # escala numérica (ex.: 0-10)
    INTEGER = "integer"      # inteiro livre (ex.: horas de sono)
    CHOICE = "choice"        # múltipla escolha (uma opção)
    BOOLEAN = "boolean"      # sim/não
    FREE_TEXT = "free_text"  # texto/áudio livre


class NotificationChannel(str, enum.Enum):
    LOG = "log"            # registra em log (default, sempre disponível)
    EMAIL = "email"        # e-mail via SMTP
    WEBHOOK = "webhook"    # POST para um endpoint (ponte genérica)
    WHATSAPP = "whatsapp"  # WhatsApp via Meta Cloud API


class NotificationStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class AuditAction(str, enum.Enum):
    CHECKIN_SUBMITTED = "checkin_submitted"
    RISK_CALCULATED = "risk_calculated"
    ALERT_CREATED = "alert_created"
    ALERT_STATUS_CHANGED = "alert_status_changed"
    ALERT_NOTIFICATION_SENT = "alert_notification_sent"
    PATIENT_CREATED = "patient_created"
    PATIENT_UPDATED = "patient_updated"
    PATIENT_TOKEN_ROTATED = "patient_token_rotated"
    PATIENT_ONBOARDING_SENT = "patient_onboarding_sent"
    PATIENT_EXPORTED = "patient_exported"
    PATIENT_DELETED = "patient_deleted"
