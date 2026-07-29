"""Testes do LLMFreeTextAnalyzer (mock da chamada ao provedor via _complete)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.models.enums import RiskLevel
from app.risk.free_text import (
    KeywordFreeTextAnalyzer,
    LLMFreeTextAnalyzer,
    get_free_text_analyzer,
)


class FakeLLM(LLMFreeTextAnalyzer):
    def __init__(self, content: str | None = None, raise_exc: bool = False) -> None:
        super().__init__()
        self._content = content
        self._raise = raise_exc

    def _complete(self, text: str) -> str:  # type: ignore[override]
        if self._raise:
            raise RuntimeError("provedor indisponível")
        assert self._content is not None
        return self._content


@pytest.fixture(autouse=True)
def _enable_llm(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")


def test_llm_red_is_mapped():
    analyzer = FakeLLM('{"level":"red","signals":["ideação suicida"]}')
    result = analyzer.analyze("relato qualquer")
    assert result.level is RiskLevel.RED
    assert any(s.startswith("IA:") for s in result.signals)


def test_llm_can_escalate_above_keyword():
    # Texto neutro para o keyword (green), mas o LLM enxerga risco.
    analyzer = FakeLLM('{"level":"orange","signals":["desânimo persistente"]}')
    result = analyzer.analyze("hoje foi um dia complicado")
    assert result.level is RiskLevel.ORANGE


def test_conservative_keeps_keyword_when_llm_underestimates():
    # keyword detecta crítico; LLM subestima (green) -> combinação mantém o maior (red).
    analyzer = FakeLLM('{"level":"green","signals":[]}')
    result = analyzer.analyze("não aguento mais viver")
    assert result.level is RiskLevel.RED


def test_llm_error_falls_back_to_keyword():
    analyzer = FakeLLM(raise_exc=True)
    # keyword pega o sinal crítico mesmo com o LLM falhando.
    assert analyzer.analyze("quero morrer").level is RiskLevel.RED
    # e não quebra em texto neutro.
    assert analyzer.analyze("tudo tranquilo hoje").level is RiskLevel.GREEN


def test_json_embedded_in_prose_is_parsed():
    analyzer = FakeLLM('Claro! Aqui: {"level":"yellow","signals":["ansiedade"]} fim.')
    assert analyzer.analyze("um pouco ansioso").level is RiskLevel.YELLOW


def test_invalid_level_falls_back():
    analyzer = FakeLLM('{"level":"roxo","signals":[]}')
    # nível inválido -> exceção interna -> fallback keyword (texto neutro -> green)
    assert analyzer.analyze("dia normal").level is RiskLevel.GREEN


def test_no_api_key_uses_keyword(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    analyzer = FakeLLM('{"level":"red","signals":["x"]}')
    # sem chave, nem chama o LLM: cai no keyword (texto neutro -> green)
    assert analyzer.analyze("dia comum").level is RiskLevel.GREEN


def test_factory_selects_llm_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "free_text_analyzer", "llm")
    assert isinstance(get_free_text_analyzer(), LLMFreeTextAnalyzer)


def test_factory_defaults_to_keyword(monkeypatch):
    monkeypatch.setattr(settings, "free_text_analyzer", "keyword")
    assert isinstance(get_free_text_analyzer(), KeywordFreeTextAnalyzer)
