"""Protocolo de acompanhamento odontológico (pós-procedimento).

Vertical de exemplo fora de saúde mental: prova que a base plugável suporta
outra especialidade. Monitora dor (EVA 0–10), sangramento, inchaço, febre e a
adesão a analgésico/antibiótico prescrito pelo dentista. Sem itens de saúde
mental (autoagressão/CVV).
"""

from __future__ import annotations

from app.models.enums import QuestionType
from app.protocol.base import QuestionDef

ODONTOLOGY_SPECIALTY = "odontologia"
ODONTOLOGY_PROTOCOL_NAME = "Protocolo Odontológico — Pós-procedimento"
ODONTOLOGY_PROTOCOL_VERSION = "1.0"

# Categorias
CAT_DOR = "Dor"
CAT_SANGRAMENTO = "Sangramento"
CAT_INCHACO = "Inchaço"
CAT_FEBRE = "Febre"
CAT_MEDICACAO = "Medicação"
CAT_LIVRE = "Livre"

# Códigos
Q_PAIN = "pain"            # EVA 0–10
Q_BLEEDING = "bleeding"
Q_SWELLING = "swelling"
Q_FEVER = "fever"
Q_MEDICATION = "medication_taken"
Q_FREE_TEXT = "free_text"

YES = "sim"
NO = "nao"
PARTIAL = "parcialmente"
# Inchaço
SW_NONE = "nenhum"
SW_MILD = "leve"
SW_MODERATE = "moderado"
SW_INTENSE = "intenso"

ODONTOLOGY_QUESTIONS: list[QuestionDef] = [
    QuestionDef(
        code=Q_PAIN,
        category=CAT_DOR,
        text="Qual seu nível de dor agora? (0 = nenhuma, 10 = pior possível)",
        type=QuestionType.SCALE,
        position=1,
        options={"min": 0, "max": 10, "direction": "higher_is_worse"},
    ),
    QuestionDef(
        code=Q_BLEEDING,
        category=CAT_SANGRAMENTO,
        text="Teve sangramento na região hoje?",
        type=QuestionType.BOOLEAN,
        position=2,
        options={"choices": [YES, NO]},
    ),
    QuestionDef(
        code=Q_SWELLING,
        category=CAT_INCHACO,
        text="Como está o inchaço?",
        type=QuestionType.CHOICE,
        position=3,
        options={"choices": [SW_NONE, SW_MILD, SW_MODERATE, SW_INTENSE]},
    ),
    QuestionDef(
        code=Q_FEVER,
        category=CAT_FEBRE,
        text="Teve febre?",
        type=QuestionType.BOOLEAN,
        position=4,
        options={"choices": [YES, NO]},
    ),
    QuestionDef(
        code=Q_MEDICATION,
        category=CAT_MEDICACAO,
        text="Tomou a medicação (analgésico/antibiótico) conforme prescrito?",
        type=QuestionType.CHOICE,
        position=5,
        options={"choices": [YES, PARTIAL, NO]},
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
