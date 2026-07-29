"""Schemas de autenticação (perfil médico)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class DoctorRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    specialty: str = Field(default="psiquiatria", max_length=120)
    clinic: str | None = Field(default=None, max_length=255)
    council_id: str | None = Field(default=None, max_length=60)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
