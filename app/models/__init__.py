"""Modelos ORM do Flowra Care.

Importados aqui para que o metadata do SQLAlchemy (e o autogenerate do Alembic)
enxerguem todas as tabelas.
"""

from app.models.alert import Alert
from app.models.audit import AuditLog
from app.models.auth_tokens import PasswordResetToken, RefreshToken
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
    TenantKind,
    UserRole,
)
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.protocol import Protocol, ProtocolQuestion
from app.models.tenant import Tenant
from app.models.user import User

__all__ = [
    "Alert",
    "AuditLog",
    "CheckIn",
    "Doctor",
    "Notification",
    "PasswordResetToken",
    "Patient",
    "Protocol",
    "ProtocolQuestion",
    "RefreshToken",
    "Tenant",
    "User",
    "AlertStatus",
    "AlertUrgency",
    "AuditAction",
    "NotificationChannel",
    "NotificationStatus",
    "QuestionType",
    "RiskLevel",
    "TenantKind",
    "UserRole",
]
