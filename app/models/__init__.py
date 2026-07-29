"""Modelos ORM do Flowra Care.

Importados aqui para que o metadata do SQLAlchemy (e o autogenerate do Alembic)
enxerguem todas as tabelas.
"""

from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.checkin import CheckIn
from app.models.doctor import Doctor
from app.models.enums import (
    AlertStatus,
    AlertUrgency,
    AuditAction,
    NotificationChannel,
    NotificationStatus,
    QuestionType,
    RiskLevel,
    UserRole,
)
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.protocol import Protocol, ProtocolQuestion
from app.models.user import User

__all__ = [
    "Alert",
    "AuditLog",
    "CheckIn",
    "Doctor",
    "Notification",
    "Patient",
    "Protocol",
    "ProtocolQuestion",
    "User",
    "AlertStatus",
    "AlertUrgency",
    "AuditAction",
    "NotificationChannel",
    "NotificationStatus",
    "QuestionType",
    "RiskLevel",
    "UserRole",
]
