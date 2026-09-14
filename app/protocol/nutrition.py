"""Protocolo de acompanhamento nutricional.

Vertical de nutrição: monitora peso, adesão ao plano alimentar, hidratação,
sintomas gastrointestinais e episódios de compulsão. Transtornos alimentares têm
comorbidade com saúde mental, então o pacote mantém o analisador de texto de
crise ligado (ver packs.py).
"""

from __future__ import annotations

from app.models.enums import QuestionType
from app.protocol.base import QuestionDef

NUTRITION_SPECIALTY = "nutricao"
NUTRITION_PROTOCOL_NAME = "Protocolo Nutricional — Acompanhamento"
NUTRITION_PROTOCOL_VERSION = "1.0"

# Categorias
CAT_PESO = "Peso"
CAT_ALIMENTACAO = "Alimentação"
CAT_HIDRATACAO = "Hidratação"
CAT_GI = "Sintomas GI"
CAT_COMPULSAO = "Compulsão"
CAT_LIVRE = "Livre"

# Códigos
Q_WEIGHT = "weight"
Q_MEAL_PLAN = "meal_plan"
Q_WATER = "water"
Q_GI = "gi_symptoms"
Q_BINGE = "binge"
Q_FREE_TEXT = "free_text"

YES = "sim"
NO = "nao"
PARTIAL = "parcialmente"
# Sintomas GI
GI_NONE = "nenhum"
GI_MILD = "leve"
GI_MODERATE = "moderado"
GI_INTENSE = "intenso"

NUTRITION_QUESTIONS: list[QuestionDef] = [
    QuestionDef(
        code=Q_WEIGHT,
        category=CAT_PESO,
        text="Qual seu peso hoje? (kg — opcional)",
        type=QuestionType.SCALE,
        position=1,
        required=False,
        options={"min": 20, "max": 400, "unit": "kg"},
    ),
    QuestionDef(
        code=Q_MEAL_PLAN,
        category=CAT_ALIMENTACAO,
        text="Você seguiu o plano alimentar hoje?",
        type=QuestionType.CHOICE,
        position=2,
        options={"choices": [YES, PARTIAL, NO]},
    ),
    QuestionDef(
        code=Q_WATER,
        category=CAT_HIDRATACAO,
        text="Quantos copos de água você bebeu?",
        type=QuestionType.INTEGER,
        position=3,
        required=False,
        options={"min": 0, "max": 30, "unit": "copos"},
    ),
    QuestionDef(
        code=Q_GI,
        category=CAT_GI,
        text="Teve sintomas no estômago/intestino (náusea, dor, prisão de ventre)?",
        type=QuestionType.CHOICE,
        position=4,
        options={"choices": [GI_NONE, GI_MILD, GI_MODERATE, GI_INTENSE]},
    ),
    QuestionDef(
        code=Q_BINGE,
        category=CAT_COMPULSAO,
        text="Teve algum episódio de compulsão alimentar hoje?",
        type=QuestionType.BOOLEAN,
        position=5,
        options={"choices": [YES, NO]},
    ),
    QuestionDef(
        code=Q_FREE_TEXT,
        category=CAT_LIVRE,
        text="Quer relatar mais alguma coisa? (opcional)",
        type=QuestionType.FREE_TEXT,
        position=6,
        required=False,
    ),
]
