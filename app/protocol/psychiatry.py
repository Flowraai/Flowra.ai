"""Definição do protocolo psiquiátrico pré-definido do MVP (seção 5 do planejamento).

Esta é a fonte única de verdade das perguntas: usada pelo seed (para criar as
linhas em `protocol_questions`) e pelo motor de risco (que lê por `code`).

IMPORTANTE (clínico): os textos, categorias e escalas abaixo são um ponto de
partida e DEVEM ser revisados com um médico consultor antes do piloto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import QuestionType

# --- Categorias (seção 5) ---
CAT_HUMOR = "Humor"
CAT_ANSIEDADE = "Ansiedade"
CAT_SONO = "Sono"
CAT_MEDICACAO = "Medicação"
CAT_CRISES = "Crises"
CAT_EFEITOS = "Efeitos colaterais"
CAT_LIVRE = "Livre"

# --- Códigos estáveis usados pelo motor de risco ---
Q_MOOD = "mood"
Q_ANXIETY = "anxiety"
Q_SLEPT_WELL = "slept_well"
Q_SLEEP_HOURS = "sleep_hours"
Q_MEDICATION = "medication_taken"
Q_CRISIS = "crisis"
Q_SIDE_EFFECTS = "side_effects"
Q_FREE_TEXT = "free_text"

# Valores canônicos para respostas de múltipla escolha.
YES = "sim"
NO = "nao"
PARTIAL = "parcialmente"
SOSO = "mais_ou_menos"


@dataclass(frozen=True)
class QuestionDef:
    code: str
    category: str
    text: str
    type: QuestionType
    position: int
    required: bool = True
    options: dict | None = None


PSYCHIATRY_PROTOCOL_NAME = "Protocolo Psiquiátrico — Acompanhamento diário"
PSYCHIATRY_PROTOCOL_VERSION = "1.0"
PSYCHIATRY_SPECIALTY = "psiquiatria"

PSYCHIATRY_QUESTIONS: list[QuestionDef] = [
    QuestionDef(
        code=Q_MOOD,
        category=CAT_HUMOR,
        text="Como você está se sentindo hoje? (0 = muito mal, 10 = muito bem)",
        type=QuestionType.SCALE,
        position=1,
        options={"min": 0, "max": 10, "direction": "higher_is_better"},
    ),
    QuestionDef(
        code=Q_ANXIETY,
        category=CAT_ANSIEDADE,
        text="Qual seu nível de ansiedade hoje? (0 = nenhuma, 10 = extrema)",
        type=QuestionType.SCALE,
        position=2,
        options={"min": 0, "max": 10, "direction": "higher_is_worse"},
    ),
    QuestionDef(
        code=Q_SLEPT_WELL,
        category=CAT_SONO,
        text="Você dormiu bem?",
        type=QuestionType.CHOICE,
        position=3,
        options={"choices": [YES, SOSO, NO]},
    ),
    QuestionDef(
        code=Q_SLEEP_HOURS,
        category=CAT_SONO,
        text="Quantas horas você dormiu?",
        type=QuestionType.INTEGER,
        position=4,
        options={"min": 0, "max": 24, "unit": "horas"},
    ),
    QuestionDef(
        code=Q_MEDICATION,
        category=CAT_MEDICACAO,
        text="Você tomou a medicação conforme prescrito?",
        type=QuestionType.CHOICE,
        position=5,
        options={"choices": [YES, PARTIAL, NO]},
    ),
    QuestionDef(
        code=Q_CRISIS,
        category=CAT_CRISES,
        text="Você teve algum episódio de crise hoje?",
        type=QuestionType.BOOLEAN,
        position=6,
        options={"choices": [YES, NO]},
    ),
    QuestionDef(
        code=Q_SIDE_EFFECTS,
        category=CAT_EFEITOS,
        text="Você sentiu algum efeito colateral?",
        type=QuestionType.BOOLEAN,
        position=7,
        options={"choices": [YES, NO]},
    ),
    QuestionDef(
        code=Q_FREE_TEXT,
        category=CAT_LIVRE,
        text="Quer contar mais alguma coisa sobre hoje?",
        type=QuestionType.FREE_TEXT,
        position=8,
        required=False,
    ),
]
