"""Agrega todas as rotas da API sob /api/v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_active_subscription
from app.api.routes import (
    admin,
    alerts,
    appointments,
    attachments,
    auth,
    billing,
    devices,
    exams,
    health,
    medications,
    messages,
    notifications,
    patient_app,
    patients,
    prescriptions,
    protocols,
)

api_router = APIRouter()
api_router.include_router(health.router)

v1 = APIRouter(prefix="/api/v1")

# Rotas sem gate de assinatura: autenticação, cobrança, admin, e fluxos do
# paciente (token de paciente, não JWT de médico).
v1.include_router(auth.router)
v1.include_router(billing.router)
v1.include_router(admin.router)
v1.include_router(patient_app.router)
v1.include_router(attachments.router)  # compartilhado (médico e paciente)
v1.include_router(devices.router)
v1.include_router(protocols.router)

# Telas clínicas do médico: exigem assinatura ativa do tenant quando
# BILLING_ENABLED=true (no-op caso contrário).
_gated = [Depends(require_active_subscription)]
v1.include_router(patients.router, dependencies=_gated)
v1.include_router(alerts.router, dependencies=_gated)
v1.include_router(notifications.router, dependencies=_gated)
v1.include_router(medications.router, dependencies=_gated)
v1.include_router(appointments.router, dependencies=_gated)
v1.include_router(exams.router, dependencies=_gated)
v1.include_router(prescriptions.router, dependencies=_gated)
v1.include_router(messages.router, dependencies=_gated)

api_router.include_router(v1)
