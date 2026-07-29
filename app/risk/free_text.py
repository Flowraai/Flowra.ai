"""Análise do texto/áudio livre do check-in (o "Módulo de IA" da arquitetura).

O contrato é `FreeTextAnalyzer.analyze(text) -> FreeTextResult`. O MVP usa por
padrão o `KeywordFreeTextAnalyzer` (determinístico, roda sem chave de API e é
auditável). A estratégia `llm` fica plugável: basta implementar `LLMFreeTextAnalyzer`
respeitando o mesmo contrato e selecioná-la via FREE_TEXT_ANALYZER=llm.

Filosofia conservadora (seção 6): preferir falso positivo a falso negativo.
Quando houver dúvida, escalar o risco.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings
from app.models.enums import RiskLevel


@dataclass
class FreeTextResult:
    level: RiskLevel = RiskLevel.GREEN
    signals: list[str] = field(default_factory=list)


class FreeTextAnalyzer(Protocol):
    def analyze(self, text: str | None) -> FreeTextResult: ...


def _normalize(text: str) -> str:
    """Minúsculas e sem acentos, para casar palavras-chave de forma robusta."""
    text = text.lower()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# Palavras/expressões em forma normalizada (sem acento). Revisar com médico consultor.
_CRITICAL_SIGNALS = [
    "me matar", "quero morrer", "queria morrer", "vontade de morrer",
    "tirar minha vida", "tirar a minha vida", "acabar com tudo",
    "acabar com a minha vida", "por fim a tudo", "nao quero viver",
    "nao quero mais viver", "nao aguento mais viver", "sem vontade de viver",
    "nao vale a pena viver", "melhor morto", "melhor morta", "suicid",
    "me machucar", "me cortar", "me ferir", "desaparecer para sempre",
    "sumir para sempre", "nao ter mais que acordar",
]
_HIGH_SIGNALS = [
    "sem esperanca", "sem saida", "desesperad", "nao aguento mais",
    "nao consigo mais", "no fundo do poco", "muito mal", "piorando muito",
    "surto", "recaida", "ataque de panico", "panico", "nao durmo ha dias",
    "cada dia pior",
]
_MODERATE_SIGNALS = [
    "triste", "ansios", "angustia", "medo", "sozinh", "chorando", "chorei",
    "cansad", "sem animo", "desanimad", "irritad", "sem forcas",
]


class KeywordFreeTextAnalyzer:
    """Analisador determinístico por palavras-chave (default do MVP)."""

    def analyze(self, text: str | None) -> FreeTextResult:
        result = FreeTextResult()
        if not text or not text.strip():
            return result

        normalized = _normalize(text)

        for level, signals, label in (
            (RiskLevel.RED, _CRITICAL_SIGNALS, "sinal crítico no texto livre"),
            (RiskLevel.ORANGE, _HIGH_SIGNALS, "sinal de piora no texto livre"),
            (RiskLevel.YELLOW, _MODERATE_SIGNALS, "sinal de atenção no texto livre"),
        ):
            matched = [kw for kw in signals if kw in normalized]
            if matched:
                result.level = level
                result.signals = [f"{label}: '{kw}'" for kw in matched]
                # Já encontramos o nível mais alto (a ordem acima é decrescente).
                break

        return result


class LLMFreeTextAnalyzer:
    """Placeholder para análise via LLM (transcrição de áudio + interpretação).

    Deve implementar o mesmo contrato e retornar `FreeTextResult`. Enquanto não
    houver integração/credenciais, cai no analisador por palavras-chave para não
    silenciar sinais de risco (falha segura, conservadora).
    """

    def __init__(self) -> None:
        self._fallback = KeywordFreeTextAnalyzer()

    def analyze(self, text: str | None) -> FreeTextResult:
        # TODO: chamar o LLM (ex.: Claude) com prompt de triagem de risco em saúde
        # mental e mapear a saída para RiskLevel. Por ora, fallback determinístico.
        return self._fallback.analyze(text)


def get_free_text_analyzer() -> FreeTextAnalyzer:
    if settings.free_text_analyzer == "llm" and settings.llm_api_key:
        return LLMFreeTextAnalyzer()
    return KeywordFreeTextAnalyzer()
