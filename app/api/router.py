"""Agrega todas as rotas da API sob /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    alerts,
    appointments,
    auth,
    exams,
    health,
    medications,
    notifications,
    patient_app,
    patients,
    protocols,
)

api_router = APIRouter()
api_router.include_router(health.router)

v1 = APIRouter(prefix="/api/v1")
v1.include_router(auth.router)
v1.include_router(patients.router)
v1.include_router(protocols.router)
v1.include_router(alerts.router)
v1.include_router(notifications.router)
v1.include_router(medications.router)
v1.include_router(appointments.router)
v1.include_router(exams.router)
v1.include_router(patient_app.router)

api_router.include_router(v1)
