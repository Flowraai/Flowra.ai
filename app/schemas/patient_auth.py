"""Schemas do login do paciente por CPF + senha (ativação, login, reset)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.security import valid_cpf

_MIN_PWD = 6


def _check_cpf(v: str) -> str:
    if not valid_cpf(v):
        raise ValueError("CPF inválido.")
    return v


class PatientAccount(BaseModel):
    """Estado da conta do paciente (o app decide qual tela mostrar)."""

    name: str
    activated: bool   # já criou senha?
    has_contact: bool  # tem WhatsApp/e-mail para receber o código de recuperação?


class PatientActivate(BaseModel):
    """Primeira entrada (via token do convite): define CPF + senha."""

    cpf: str
    password: str = Field(min_length=_MIN_PWD, max_length=128)

    _cpf = field_validator("cpf")(_check_cpf)


class PatientLogin(BaseModel):
    cpf: str
    password: str = Field(min_length=1, max_length=128)

    _cpf = field_validator("cpf")(_check_cpf)


class PatientForgot(BaseModel):
    cpf: str

    _cpf = field_validator("cpf")(_check_cpf)


class PatientReset(BaseModel):
    cpf: str
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=_MIN_PWD, max_length=128)

    _cpf = field_validator("cpf")(_check_cpf)


class PatientSession(BaseModel):
    """Token de sessão emitido após ativar/entrar (o app guarda e usa em X-Patient-Token)."""

    access_token: str
