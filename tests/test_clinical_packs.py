"""Registry de pacotes clínicos por especialidade (resolução, fallback, paridade)."""

from __future__ import annotations

from app.clinical.packs import (
    CLINICAL_PACKS,
    DEFAULT_PACK,
    ClinicalPack,
    get_pack,
)
from app.models.enums import RiskLevel
from app.protocol import psychiatry as P
from app.risk.engine import PsychiatricRiskEngine, RiskThresholds
from app.risk.rules import NumericRule


def test_resolution_and_fallback():
    assert get_pack("psiquiatria") is CLINICAL_PACKS["psiquiatria"]
    assert get_pack("PSIQUIATRIA").key == "psiquiatria"  # case-insensitive
    assert get_pack(None) is DEFAULT_PACK               # sem especialidade → default
    assert get_pack("fisioterapia") is DEFAULT_PACK      # desconhecida → default (psiquiatria)


def test_psychiatry_pack_scales_and_features():
    pack = get_pack("psiquiatria")
    assert [s.code for s in pack.scales()] == ["phq9", "gad7"]
    assert pack.has_feature("medicacao") is True
    assert pack.safety_message and "188" in pack.safety_message


def test_pack_engine_parity_with_psychiatric_engine():
    # O motor montado pelo pacote deve dar o MESMO resultado do PsychiatricRiskEngine.
    pack = get_pack("psiquiatria")
    pack_engine = pack.build_engine()
    legacy = PsychiatricRiskEngine()
    cases = [
        {P.Q_MOOD: 8, P.Q_ANXIETY: 2},
        {P.Q_MOOD: 1},
        {P.Q_ANXIETY: 10},
        {P.Q_SELF_HARM: P.YES},
        {P.Q_MEDICATION: P.NO},
        {},
    ]
    for r in cases:
        a = pack_engine.assess(r)
        b = legacy.assess(r)
        assert a.level is b.level and a.reasons == b.reasons and a.category_risks == b.category_risks


def test_a_second_pack_changes_rules_and_scales():
    # Prova a plugabilidade: um pacote fictício de outra especialidade muda regras/escalas.
    def dor_rules(_t: RiskThresholds):
        return [NumericRule("dor", [(">=", 8, RiskLevel.RED, "dor intensa ({v:g}/10)")])]

    odonto = ClinicalPack(
        key="odontologia-teste", label="Odonto (teste)", specialty="odontologia-teste",
        protocol_name="x", protocol_version="1", protocol_description="x",
        questions=(), scale_codes=(), rules_factory=dor_rules,
        free_text_category="Livre", features={"medicacao": False}, safety_message=None,
    )
    try:
        CLINICAL_PACKS[odonto.specialty] = odonto
        p = get_pack("odontologia-teste")
        assert p.has_feature("medicacao") is False
        assert p.scales() == []
        eng = p.build_engine()
        assert eng.assess({"dor": 9}).level is RiskLevel.RED
        assert eng.assess({P.Q_SELF_HARM: P.YES}).level is RiskLevel.GREEN  # não conhece autolesão
    finally:
        CLINICAL_PACKS.pop("odontologia-teste", None)
