"""Motor de risco psiquiátrico (índice 🟢🟡🟠🔴).

Regras determinísticas por categoria + análise do texto livre, combinadas de
forma CONSERVADORA: o risco final é sempre o MAIOR entre todas as contribuições
(seção 6: preferir falso positivo a falso negativo).

Os limiares ficam em `RiskThresholds` para serem ajustados junto a um médico
consultor sem tocar na lógica. A função é pura (sem I/O), portanto testável.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import RiskLevel
from app.protocol import psychiatry as P
from app.risk.free_text import FreeTextAnalyzer, KeywordFreeTextAnalyzer

# Mapa código -> categoria (para reportar risco por categoria no check-in).
_CODE_CATEGORY = {q.code: q.category for q in P.PSYCHIATRY_QUESTIONS}


@dataclass
class RiskThresholds:
    # Humor (0-10, maior é melhor)
    mood_red_at_or_below: int = 2
    mood_orange_at_or_below: int = 4
    mood_yellow_at_or_below: int = 5
    # Ansiedade (0-10, maior é pior)
    anxiety_orange_at_or_above: int = 9
    anxiety_yellow_at_or_above: int = 6
    # Sono (horas)
    sleep_hours_orange_below: int = 3
    sleep_hours_yellow_below: int = 5


@dataclass
class RiskAssessment:
    level: RiskLevel = RiskLevel.GREEN
    reasons: list[str] = field(default_factory=list)
    category_risks: dict[str, str] = field(default_factory=dict)
    free_text_signals: list[str] = field(default_factory=list)


def _is_yes(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {P.YES, "yes", "true", "1"}
    return False


def _as_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _as_choice(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, bool):
        return P.YES if value else P.NO
    return None


class PsychiatricRiskEngine:
    """Avalia o risco de um check-in psiquiátrico."""

    def __init__(
        self,
        thresholds: RiskThresholds | None = None,
        free_text_analyzer: FreeTextAnalyzer | None = None,
    ) -> None:
        self.t = thresholds or RiskThresholds()
        self.analyzer = free_text_analyzer or KeywordFreeTextAnalyzer()

    def assess(
        self, structured_responses: dict, free_text: str | None = None
    ) -> RiskAssessment:
        assessment = RiskAssessment()
        r = structured_responses or {}

        def contribute(code: str, level: RiskLevel, reason: str) -> None:
            if level is RiskLevel.GREEN:
                return
            category = _CODE_CATEGORY.get(code, code)
            assessment.level = assessment.level.escalate(level)
            assessment.reasons.append(reason)
            current = assessment.category_risks.get(category)
            if current is None or RiskLevel(current).order < level.order:
                assessment.category_risks[category] = level.value

        # --- Humor ---
        mood = _as_number(r.get(P.Q_MOOD))
        if mood is not None:
            if mood <= self.t.mood_red_at_or_below:
                contribute(P.Q_MOOD, RiskLevel.RED, f"humor muito baixo ({mood:g}/10)")
            elif mood <= self.t.mood_orange_at_or_below:
                contribute(P.Q_MOOD, RiskLevel.ORANGE, f"humor baixo ({mood:g}/10)")
            elif mood <= self.t.mood_yellow_at_or_below:
                contribute(P.Q_MOOD, RiskLevel.YELLOW, f"humor rebaixado ({mood:g}/10)")

        # --- Ansiedade ---
        anxiety = _as_number(r.get(P.Q_ANXIETY))
        if anxiety is not None:
            if anxiety >= self.t.anxiety_orange_at_or_above:
                contribute(P.Q_ANXIETY, RiskLevel.ORANGE, f"ansiedade muito alta ({anxiety:g}/10)")
            elif anxiety >= self.t.anxiety_yellow_at_or_above:
                contribute(P.Q_ANXIETY, RiskLevel.YELLOW, f"ansiedade elevada ({anxiety:g}/10)")

        # --- Sono ---
        slept_well = _as_choice(r.get(P.Q_SLEPT_WELL))
        if slept_well == P.NO:
            contribute(P.Q_SLEPT_WELL, RiskLevel.YELLOW, "relato de sono ruim")
        hours = _as_number(r.get(P.Q_SLEEP_HOURS))
        if hours is not None:
            if hours < self.t.sleep_hours_orange_below:
                contribute(P.Q_SLEEP_HOURS, RiskLevel.ORANGE, f"sono muito reduzido ({hours:g}h)")
            elif hours < self.t.sleep_hours_yellow_below:
                contribute(P.Q_SLEEP_HOURS, RiskLevel.YELLOW, f"poucas horas de sono ({hours:g}h)")

        # --- Medicação (adesão) ---
        medication = _as_choice(r.get(P.Q_MEDICATION))
        if medication == P.NO:
            contribute(P.Q_MEDICATION, RiskLevel.ORANGE, "não tomou a medicação prescrita")
        elif medication == P.PARTIAL:
            contribute(P.Q_MEDICATION, RiskLevel.YELLOW, "tomou a medicação parcialmente")

        # --- Crises ---
        if _is_yes(r.get(P.Q_CRISIS)):
            contribute(P.Q_CRISIS, RiskLevel.RED, "episódio de crise relatado")

        # --- Efeitos colaterais ---
        if _is_yes(r.get(P.Q_SIDE_EFFECTS)):
            contribute(P.Q_SIDE_EFFECTS, RiskLevel.YELLOW, "efeito colateral relatado")

        # --- Texto/áudio livre (Módulo de IA) ---
        free_result = self.analyzer.analyze(free_text)
        if free_result.level is not RiskLevel.GREEN:
            assessment.level = assessment.level.escalate(free_result.level)
            assessment.reasons.extend(free_result.signals)
            assessment.free_text_signals = free_result.signals
            category = P.CAT_LIVRE
            current = assessment.category_risks.get(category)
            if current is None or RiskLevel(current).order < free_result.level.order:
                assessment.category_risks[category] = free_result.level.value

        return assessment
