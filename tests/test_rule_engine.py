"""Motor de risco genérico orientado a regras (base para pacotes por especialidade)."""

from __future__ import annotations

from app.models.enums import RiskLevel
from app.risk.rules import ChoiceRule, NumericRule, RuleRiskEngine, YesRule


def _engine(rules, category_map=None):
    # Sem analisador de texto real: nada a extrair de free_text=None → verde.
    return RuleRiskEngine(rules=rules, category_map=category_map or {}, free_text_category="Livre")


def test_numeric_rule_first_matching_band_wins():
    # Regra "maior = pior" (ex.: dor EVA 0–10) — prova que outra especialidade pluga.
    rule = NumericRule("dor", [
        (">=", 8, RiskLevel.RED, "dor intensa ({v:g}/10)"),
        (">=", 5, RiskLevel.ORANGE, "dor moderada ({v:g}/10)"),
        (">=", 3, RiskLevel.YELLOW, "dor leve ({v:g}/10)"),
    ])
    eng = _engine([rule], {"dor": "Dor"})
    assert eng.assess({"dor": 9}).level is RiskLevel.RED
    assert eng.assess({"dor": 6}).level is RiskLevel.ORANGE
    assert eng.assess({"dor": 3}).level is RiskLevel.YELLOW
    assert eng.assess({"dor": 1}).level is RiskLevel.GREEN
    # motivo formatado a partir do valor + categoria reportada
    a = eng.assess({"dor": 9})
    assert a.reasons == ["dor intensa (9/10)"] and a.category_risks["Dor"] == "red"


def test_numeric_rule_lower_is_worse():
    rule = NumericRule("humor", [("<=", 2, RiskLevel.RED, "muito baixo ({v:g})")])
    eng = _engine([rule])
    assert eng.assess({"humor": 2}).level is RiskLevel.RED
    assert eng.assess({"humor": 3}).level is RiskLevel.GREEN


def test_yes_rule():
    eng = _engine([YesRule("sangramento", RiskLevel.RED, "sangramento pós-op")])
    assert eng.assess({"sangramento": "sim"}).level is RiskLevel.RED
    assert eng.assess({"sangramento": True}).level is RiskLevel.RED
    assert eng.assess({"sangramento": "nao"}).level is RiskLevel.GREEN


def test_choice_rule_maps_each_option():
    eng = _engine([ChoiceRule("uso", {
        "nao": (RiskLevel.ORANGE, "não usou"),
        "parcialmente": (RiskLevel.YELLOW, "uso parcial"),
    })])
    assert eng.assess({"uso": "nao"}).level is RiskLevel.ORANGE
    assert eng.assess({"uso": "parcialmente"}).level is RiskLevel.YELLOW
    assert eng.assess({"uso": "sim"}).level is RiskLevel.GREEN


def test_conservative_combination_takes_highest():
    eng = _engine([
        NumericRule("dor", [(">=", 5, RiskLevel.YELLOW, "dor {v:g}")]),
        YesRule("febre", RiskLevel.ORANGE, "febre"),
    ])
    a = eng.assess({"dor": 6, "febre": "sim"})
    assert a.level is RiskLevel.ORANGE  # laranja > amarelo
    assert len(a.reasons) == 2


def test_missing_and_unknown_do_not_crash():
    eng = _engine([NumericRule("dor", [(">=", 5, RiskLevel.RED, "d {v:g}")])])
    assert eng.assess({}).level is RiskLevel.GREEN
    assert eng.assess({"dor": "n/a"}).level is RiskLevel.GREEN
