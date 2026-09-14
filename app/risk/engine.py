"""Motor de risco psiquiátrico (índice 🟢🟡🟠🔴).

Conjunto de regras da especialidade PSIQUIATRIA, montado sobre o `RuleRiskEngine`
genérico (`app/risk/rules.py`). As regras são declarativas e combinadas de forma
CONSERVADORA: o risco final é sempre o MAIOR entre as contribuições
(seção 6: preferir falso positivo a falso negativo).

Os limiares ficam em `RiskThresholds` para ajuste junto a um médico consultor sem
tocar na lógica. `PsychiatricRiskEngine` preserva a assinatura anterior; a lógica
agora vive nas regras — o que abre caminho para pacotes por especialidade.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import RiskLevel
from app.protocol import psychiatry as P
from app.risk.free_text import FreeTextAnalyzer
from app.risk.rules import (
    ChoiceRule,
    NumericRule,
    RiskAssessment,
    Rule,
    RuleRiskEngine,
    YesRule,
)

__all__ = [
    "RiskThresholds", "RiskAssessment", "PsychiatricRiskEngine",
    "psychiatry_rules", "psychology_rules",
]

# Mapa código -> categoria (para reportar risco por categoria no check-in).
_CODE_CATEGORY = {q.code: q.category for q in P.PSYCHIATRY_QUESTIONS}


@dataclass
class RiskThresholds:
    # Humor (0-10, maior é melhor)
    mood_red_at_or_below: int = 2
    mood_orange_at_or_below: int = 4
    mood_yellow_at_or_below: int = 5
    # Ansiedade (0-10, maior é pior)
    anxiety_red_at_or_above: int = 10
    anxiety_orange_at_or_above: int = 9
    anxiety_yellow_at_or_above: int = 6
    # Sono (horas)
    sleep_hours_orange_below: int = 3
    sleep_hours_yellow_below: int = 5


def psychiatry_rules(t: RiskThresholds) -> list[Rule]:
    """Regras de risco de psiquiatria (mesma ordem e limiares de antes)."""
    return [
        # Ideação/autoagressão (CL-1): item obrigatório — "sim" força VERMELHO.
        YesRule(P.Q_SELF_HARM, RiskLevel.RED,
                "pensamentos de autoagressão/ideação suicida relatados"),
        NumericRule(P.Q_MOOD, [
            ("<=", t.mood_red_at_or_below, RiskLevel.RED, "humor muito baixo ({v:g}/10)"),
            ("<=", t.mood_orange_at_or_below, RiskLevel.ORANGE, "humor baixo ({v:g}/10)"),
            ("<=", t.mood_yellow_at_or_below, RiskLevel.YELLOW, "humor rebaixado ({v:g}/10)"),
        ]),
        NumericRule(P.Q_ANXIETY, [
            (">=", t.anxiety_red_at_or_above, RiskLevel.RED, "ansiedade máxima ({v:g}/10)"),
            (">=", t.anxiety_orange_at_or_above, RiskLevel.ORANGE, "ansiedade muito alta ({v:g}/10)"),
            (">=", t.anxiety_yellow_at_or_above, RiskLevel.YELLOW, "ansiedade elevada ({v:g}/10)"),
        ]),
        ChoiceRule(P.Q_SLEPT_WELL, {P.NO: (RiskLevel.YELLOW, "relato de sono ruim")}),
        NumericRule(P.Q_SLEEP_HOURS, [
            ("<", t.sleep_hours_orange_below, RiskLevel.ORANGE, "sono muito reduzido ({v:g}h)"),
            ("<", t.sleep_hours_yellow_below, RiskLevel.YELLOW, "poucas horas de sono ({v:g}h)"),
        ]),
        ChoiceRule(P.Q_MEDICATION, {
            P.NO: (RiskLevel.ORANGE, "não tomou a medicação prescrita"),
            P.PARTIAL: (RiskLevel.YELLOW, "tomou a medicação parcialmente"),
        }),
        YesRule(P.Q_CRISIS, RiskLevel.RED, "episódio de crise relatado"),
        YesRule(P.Q_SIDE_EFFECTS, RiskLevel.YELLOW, "efeito colateral relatado"),
    ]


def psychology_rules(t: RiskThresholds) -> list[Rule]:
    """Regras de psicologia: iguais às de psiquiatria, sem medicação/efeitos
    colaterais (o psicólogo não prescreve). Humor, ansiedade, sono, crise e
    autoagressão continuam valendo."""
    drop = {P.Q_MEDICATION, P.Q_SIDE_EFFECTS}
    return [r for r in psychiatry_rules(t) if getattr(r, "code", None) not in drop]


class PsychiatricRiskEngine(RuleRiskEngine):
    """Avalia o risco de um check-in psiquiátrico (mesma API de antes)."""

    def __init__(
        self,
        thresholds: RiskThresholds | None = None,
        free_text_analyzer: FreeTextAnalyzer | None = None,
    ) -> None:
        super().__init__(
            rules=psychiatry_rules(thresholds or RiskThresholds()),
            category_map=_CODE_CATEGORY,
            free_text_analyzer=free_text_analyzer,
            free_text_category=P.CAT_LIVRE,
        )
