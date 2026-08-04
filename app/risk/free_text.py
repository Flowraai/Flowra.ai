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


_LLM_SYSTEM_PROMPT = (
    "Você é um triador de risco em saúde mental. Leia o relato livre de um paciente "
    "psiquiátrico e classifique o risco em um destes níveis: green (estável), "
    "yellow (atenção), orange (piora/acompanhamento), red (risco relevante, ex.: "
    "ideação suicida, autoagressão, crise). Seja CONSERVADOR: na dúvida, escale o nível. "
    "Você NÃO diagnostica; apenas sinaliza risco. Responda ESTRITAMENTE em JSON: "
    '{"level":"green|yellow|orange|red","signals":["trecho ou motivo", ...]}.'
)

_LEVEL_BY_NAME = {level.value: level for level in RiskLevel}


class LLMFreeTextAnalyzer:
    """Análise via LLM (endpoint compatível com a API OpenAI).

    Combina o resultado do LLM com o analisador determinístico de forma
    conservadora (mantém o MAIOR risco). Qualquer erro/ausência de configuração
    faz cair no determinístico — nunca silencia um sinal (falha segura).

    Roda de forma síncrona (usa httpx.Client); o chamador deve invocá-la fora do
    event loop (ex.: asyncio.to_thread) para não bloqueá-lo.
    """

    def __init__(self) -> None:
        self._fallback = KeywordFreeTextAnalyzer()

    def analyze(self, text: str | None) -> FreeTextResult:
        baseline = self._fallback.analyze(text)
        if not text or not text.strip() or not settings.llm_available:
            return baseline

        try:
            llm = self._analyze_with_llm(text)
        except Exception:  # noqa: BLE001 — falha do LLM não pode silenciar risco
            return baseline

        # Combinação conservadora: maior risco entre LLM e determinístico.
        level = baseline.level.escalate(llm.level)
        signals = llm.signals + [s for s in baseline.signals if s not in llm.signals]
        return FreeTextResult(level=level, signals=signals)

    def _analyze_with_llm(self, text: str) -> FreeTextResult:
        content = self._complete(text)
        data = self._parse_json(content)
        level = _LEVEL_BY_NAME.get(str(data.get("level", "")).lower())
        if level is None:
            raise ValueError(f"nível inválido do LLM: {data!r}")
        signals = data.get("signals") or []
        if isinstance(signals, str):
            signals = [signals]
        return FreeTextResult(level=level, signals=[f"IA: {s}" for s in signals])

    def _complete(self, text: str) -> str:
        """Chama o endpoint (compatível com OpenAI) e retorna o conteúdo textual."""
        import httpx

        resp = httpx.Client(timeout=settings.llm_timeout_seconds).post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.llm_model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_json(content: str) -> dict:
        import json

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start, end = content.find("{"), content.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(content[start : end + 1])
            raise


def get_free_text_analyzer() -> FreeTextAnalyzer:
    if settings.free_text_analyzer == "llm" and settings.llm_available:
        return LLMFreeTextAnalyzer()
    return KeywordFreeTextAnalyzer()
