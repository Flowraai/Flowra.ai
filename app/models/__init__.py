"""Modelos ORM do Flowra Care.

Importados aqui para que o metadata do SQLAlchemy (e o autogenerate do Alembic)
enxerguem todas as tabelas.
"""

from app.models.alert import Alert
from app.models.appointment import Appointment
from app.models.attachment import Attachment
from app.models.audit import AuditLog
from app.models.auth_tokens import PasswordResetToken, RefreshToken
from app.models.checkin import CheckIn
from app.models.device_token import DeviceToken
from app.models.doctor import Doctor
from app.models.exam import Exam
from app.models.enums import (
    AlertStatus,
    AlertUrgency,
    AppointmentKind,
    AppointmentStatus,
    AuditAction,
    DeviceOwnerType,
    ExamStatus,
    MedicationIntakeStatus,
    MessageSender,
    MessageThread,
    NotificationChannel,
    NotificationStatus,
    PrescriptionStatus,
    QuestionType,
    RiskLevel,
    SubscriptionStatus,
    TenantKind,
    UserRole,
)
from app.models.medication import MedicationIntake, MedicationPlan
from app.models.message import Message
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.plan import Plan
from app.models.prescription import Prescription
from app.models.protocol import Protocol, ProtocolQuestion
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User

__all__ = [
    "Alert",
    "Appointment",
    "Attachment",
    "AuditLog",
    "CheckIn",
    "DeviceToken",
    "Doctor",
    "Exam",
    "MedicationIntake",
    "MedicationPlan",
    "Message",
    "Notification",
    "PasswordResetToken",
    "Patient",
    "Plan",
    "Prescription",
    "Protocol",
    "ProtocolQuestion",
    "RefreshToken",
    "Subscription",
    "Tenant",
    "User",
    "AlertStatus",
    "AlertUrgency",
    "AppointmentKind",
    "AppointmentStatus",
    "AuditAction",
    "DeviceOwnerType",
    "ExamStatus",
    "MedicationIntakeStatus",
    "MessageSender",
    "MessageThread",
    "NotificationChannel",
    "NotificationStatus",
    "PrescriptionStatus",
    "QuestionType",
    "RiskLevel",
    "SubscriptionStatus",
    "TenantKind",
    "UserRole",
]
