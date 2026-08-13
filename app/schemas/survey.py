"""Schemas do editor de pesquisa (protocolo editável pelo médico)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import QuestionType


class SurveyQuestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    category: str
    text: str
    type: QuestionType
    position: int
    required: bool
    options: dict | None = None
    protected: bool = False  # pergunta de segurança: edita, mas não remove


class Survey(BaseModel):
    id: uuid.UUID
    name: str
    questions: list[SurveyQuestion]


class SurveyQuestionCreate(BaseModel):
    text: str = Field(min_length=1)
    category: str = Field(default="Personalizado", max_length=60)
    type: QuestionType
    required: bool = True
    # Metadados por tipo: scale → {min,max,direction,scale_style}; choice → {choices};
    # integer → {min,max,unit}. O backend completa os emojis quando for escala-emoji.
    options: dict | None = None


class SurveyQuestionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=60)
    required: bool | None = None
    position: int | None = Field(default=None, ge=0)
    # Alterna a apresentação de uma escala: "number" (0–10) ou "emoji".
    scale_style: str | None = None


class SurveyReorder(BaseModel):
    order: list[uuid.UUID] = Field(min_length=1)
