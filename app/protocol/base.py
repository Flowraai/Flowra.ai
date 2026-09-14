"""Tipos base do protocolo de check-in, compartilhados entre especialidades."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import QuestionType


@dataclass(frozen=True)
class QuestionDef:
    code: str
    category: str
    text: str
    type: QuestionType
    position: int
    required: bool = True
    options: dict | None = None
