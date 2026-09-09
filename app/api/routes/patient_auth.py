"""Login do paciente por CPF + senha (ativação, entrada, recuperação por código)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_patient
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.core.security import hash_cpf, hash_password, verify_password
from app.db.session import get_db
from app.models.patient import Patient
from app.schemas.patient_auth import (
    PatientAccount,
    PatientActivate,
    PatientForgot,
    PatientLogin,
    PatientReset,
    PatientSession,
)
from app.services import patient_auth_service as pauth
from app.services.notifications import deliver_to_patient

router = APIRouter(prefix="/patient", tags=["patient-auth"])

_login_limit = rate_limit(
    settings.login_rate_limit_attempts, settings.login_rate_limit_window_seconds, "patient_login"
)
_reset_limit = rate_limit(
    settings.password_reset_rate_limit_attempts,
    settings.login_rate_limit_window_seconds,
    "patient_reset",
)

_GENERIC_LOGIN_ERR = "CPF ou senha incorretos."


@router.get("/account", response_model=PatientAccount)
async def account(patient: Patient = Depends(get_current_patient)) -> PatientAccount:
    """Estado da conta — o app decide entre 'criar acesso' e 'entrar'."""
    return PatientAccount(
        name=patient.name,
        activated=patient.password_hash is not None,
        has_contact=bool(patient.contact),
    )


@router.post("/activate", response_model=PatientSession)
async def activate(
    payload: PatientActivate,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> PatientSession:
    """Primeira entrada (via token do convite): define CPF + senha e abre a sessão."""
    if patient.password_hash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Acesso já criado. Entre com seu CPF e senha.",
        )
    if await pauth.cpf_in_use(session, hash_cpf(payload.cpf), patient.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este CPF já possui um acesso. Fale com seu médico.",
        )
    pauth.set_credentials(patient, payload.cpf, payload.password)
    token = pauth.mint_session_token(patient)
    return PatientSession(access_token=token)


@router.post("/login", response_model=PatientSession, dependencies=[Depends(_login_limit)])
async def login(
    payload: PatientLogin,
    session: AsyncSession = Depends(get_db),
) -> PatientSession:
    patient = await pauth.find_by_cpf(session, payload.cpf)
    if patient is None or not patient.password_hash or not verify_password(
        payload.password, patient.password_hash
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERR)
    token = pauth.mint_session_token(patient)
    return PatientSession(access_token=token)


@router.post("/forgot-password", dependencies=[Depends(_reset_limit)])
async def forgot_password(
    payload: PatientForgot,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Envia um código de recuperação ao contato do paciente. Resposta sempre genérica."""
    patient = await pauth.find_by_cpf(session, payload.cpf)
    if patient is not None and patient.contact:
        code = pauth.new_reset_code(patient)
        await deliver_to_patient(
            session, patient,
            subject="[Flowra Care] Código de recuperação",
            body=(
                f"Seu código para redefinir a senha é: {code}\n"
                f"Ele vale por {pauth.RESET_CODE_TTL_MINUTES} minutos. "
                "Se não foi você, ignore esta mensagem."
            ),
        )
    return {"message": "Se o CPF tiver uma conta, enviaremos um código ao contato cadastrado."}


@router.post("/reset-password", response_model=PatientSession, dependencies=[Depends(_reset_limit)])
async def reset_password(
    payload: PatientReset,
    session: AsyncSession = Depends(get_db),
) -> PatientSession:
    patient = await pauth.find_by_cpf(session, payload.cpf)
    if patient is None or not pauth.check_reset_code(patient, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido ou expirado. Peça um novo.",
        )
    patient.password_hash = hash_password(payload.new_password)
    pauth.clear_reset_code(patient)
    token = pauth.mint_session_token(patient)
    return PatientSession(access_token=token)
