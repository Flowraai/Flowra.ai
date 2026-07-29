"""Testes do analisador de texto livre por palavras-chave."""

from __future__ import annotations

from app.models.enums import RiskLevel
from app.risk.free_text import KeywordFreeTextAnalyzer

analyzer = KeywordFreeTextAnalyzer()


def test_empty_text_is_green():
    assert analyzer.analyze(None).level is RiskLevel.GREEN
    assert analyzer.analyze("   ").level is RiskLevel.GREEN


def test_neutral_text_is_green():
    result = analyzer.analyze("hoje foi um dia tranquilo, tudo certo")
    assert result.level is RiskLevel.GREEN


def test_suicidal_ideation_is_red():
    result = analyzer.analyze("não aguento mais viver assim")
    assert result.level is RiskLevel.RED
    assert result.signals


def test_accents_are_ignored():
    # Sem acentos deve casar igual.
    assert analyzer.analyze("quero morrer").level is RiskLevel.RED


def test_distress_is_orange():
    result = analyzer.analyze("estou me sentindo sem esperança")
    assert result.level is RiskLevel.ORANGE


def test_mild_is_yellow():
    result = analyzer.analyze("acordei um pouco triste hoje")
    assert result.level is RiskLevel.YELLOW
