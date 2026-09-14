"""Motor de risco orientado a regras (genérico, plugável por especialidade).

O comportamento clínico deixa de ser `if/else` cravado em psiquiatria e passa a
ser uma LISTA de regras declarativas que cada especialidade fornece (ver
`app/risk/engine.py` para o conjunto de psiquiatria). O `RuleRiskEngine` só
executa as regras e combina de forma conservadora (sempre o MAIOR risco), além
de tratar o texto livre e o áudio não analisado — partes genéricas.

Função pura (sem I/O), portanto testável.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.models.enums import RiskLevel
from app.risk.free_text import FreeTextAnalyzer, KeywordFreeTextAnalyzer

# Rótulos de resposta usados nas regras de escolha/sim-não (normalizados).
YES_TOKENS = {"sim", "yes", "true", "1"}


def is_yes(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in YES_TOKENS
    return False


def as_number(value: object) -> float | None:
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


def as_choice(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, bool):
        return "sim" if value else "nao"
    return None


@dataclass
class Contribution:
    """Uma contribuição de risco de uma regra: código, nível e o motivo legível."""

    code: str
    level: RiskLevel
    reason: str


class Rule(Protocol):
    def evaluate(self, responses: dict) -> Contribution | None: ...


@dataclass
class NumericRule:
    """Regra numérica com faixas ordenadas; a PRIMEIRA que casa vence.

    Cada faixa é (op, limiar, nível, template) — op em "<=", ">=", "<", ">".
    O template usa `{v:g}` para o valor (ex.: "humor muito baixo ({v:g}/10)").
    """

    code: str
    bands: list[tuple[str, float, RiskLevel, str]]

    def evaluate(self, responses: dict) -> Contribution | None:
        v = as_number(responses.get(self.code))
        if v is None:
            return None
        for op, threshold, level, template in self.bands:
            if _cmp(v, op, threshold):
                return Contribution(self.code, level, template.format(v=v))
        return None


@dataclass
class YesRule:
    """Um "sim" no código contribui com o nível informado."""

    code: str
    level: RiskLevel
    reason: str

    def evaluate(self, responses: dict) -> Contribution | None:
        if is_yes(responses.get(self.code)):
            return Contribution(self.code, self.level, self.reason)
        return None


@dataclass
class ChoiceRule:
    """Mapa de escolha (normalizada) -> (nível, motivo)."""

    code: str
    mapping: dict[str, tuple[RiskLevel, str]]

    def evaluate(self, responses: dict) -> Contribution | None:
        choice = as_choice(responses.get(self.code))
        if choice is None:
            return None
        hit = self.mapping.get(choice)
        if hit is None:
            return None
        level, reason = hit
        return Contribution(self.code, level, reason)


def _cmp(v: float, op: str, threshold: float) -> bool:
    if op == "<=":
        return v <= threshold
    if op == ">=":
        return v >= threshold
    if op == "<":
        return v < threshold
    if op == ">":
        return v > threshold
    raise ValueError(f"operador inválido: {op!r}")


@dataclass
class RiskAssessment:
    level: RiskLevel = RiskLevel.GREEN
    reasons: list[str] = field(default_factory=list)
    category_risks: dict[str, str] = field(default_factory=dict)
    free_text_signals: list[str] = field(default_factory=list)


class RuleRiskEngine:
    """Executa uma lista de regras + texto livre, combinando de forma conservadora."""

    def __init__(
        self,
        rules: list[Rule],
        category_map: dict[str, str],
        free_text_analyzer: FreeTextAnalyzer | None = None,
        free_text_category: str = "Livre",
    ) -> None:
        self.rules = rules
        self.category_map = category_map
        self.analyzer = free_text_analyzer or KeywordFreeTextAnalyzer()
        self.free_text_category = free_text_category

    def _bump_category(self, assessment: RiskAssessment, category: str, level: RiskLevel) -> None:
        current = assessment.category_risks.get(category)
        if current is None or RiskLevel(current).order < level.order:
            assessment.category_risks[category] = level.value

    def _contribute(self, assessment: RiskAssessment, c: Contribution) -> None:
        if c.level is RiskLevel.GREEN:
            return
        assessment.level = assessment.level.escalate(c.level)
        assessment.reasons.append(c.reason)
        category = self.category_map.get(c.code, c.code)
        self._bump_category(assessment, category, c.level)

    def assess(
        self,
        structured_responses: dict,
        free_text: str | None = None,
        *,
        audio_unanalyzed: bool = False,
    ) -> RiskAssessment:
        assessment = RiskAssessment()
        r = structured_responses or {}

        for rule in self.rules:
            c = rule.evaluate(r)
            if c is not None:
                self._contribute(assessment, c)

        # --- Texto/áudio livre (Módulo de IA) ---
        free_result = self.analyzer.analyze(free_text)
        if free_result.level is not RiskLevel.GREEN:
            assessment.level = assessment.level.escalate(free_result.level)
            assessment.reasons.extend(free_result.signals)
            assessment.free_text_signals = free_result.signals
            self._bump_category(assessment, self.free_text_category, free_result.level)

        # --- Áudio não analisado (CL-2): piso amarelo, nunca rebaixa risco maior ---
        if audio_unanalyzed:
            assessment.level = assessment.level.escalate(RiskLevel.YELLOW)
            assessment.reasons.append("áudio não analisado — revisar manualmente")
            self._bump_category(assessment, self.free_text_category, RiskLevel.YELLOW)

        return assessment
