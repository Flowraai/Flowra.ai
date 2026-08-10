"""Testes do motor de risco psiquiátrico (lógica pura, sem banco)."""

from __future__ import annotations

from app.models.enums import RiskLevel
from app.protocol import psychiatry as P
from app.risk.engine import PsychiatricRiskEngine

engine = PsychiatricRiskEngine()


def _stable_responses() -> dict:
    return {
        P.Q_MOOD: 8,
        P.Q_ANXIETY: 2,
        P.Q_SLEPT_WELL: P.YES,
        P.Q_SLEEP_HOURS: 8,
        P.Q_MEDICATION: P.YES,
        P.Q_CRISIS: P.NO,
        P.Q_SIDE_EFFECTS: P.NO,
    }


def test_stable_checkin_is_green():
    result = engine.assess(_stable_responses())
    assert result.level is RiskLevel.GREEN
    assert result.reasons == []
    assert result.category_risks == {}


def test_crisis_forces_red():
    r = _stable_responses()
    r[P.Q_CRISIS] = P.YES
    result = engine.assess(r)
    assert result.level is RiskLevel.RED
    assert result.category_risks[P.CAT_CRISES] == RiskLevel.RED.value


def test_very_low_mood_is_red():
    r = _stable_responses()
    r[P.Q_MOOD] = 1
    result = engine.assess(r)
    assert result.level is RiskLevel.RED


def test_low_mood_is_orange():
    r = _stable_responses()
    r[P.Q_MOOD] = 4
    result = engine.assess(r)
    assert result.level is RiskLevel.ORANGE


def test_medication_not_taken_is_orange():
    r = _stable_responses()
    r[P.Q_MEDICATION] = P.NO
    result = engine.assess(r)
    assert result.level is RiskLevel.ORANGE
    assert result.category_risks[P.CAT_MEDICACAO] == RiskLevel.ORANGE.value


def test_partial_medication_is_yellow():
    r = _stable_responses()
    r[P.Q_MEDICATION] = P.PARTIAL
    result = engine.assess(r)
    assert result.level is RiskLevel.YELLOW


def test_low_sleep_hours_is_orange():
    r = _stable_responses()
    r[P.Q_SLEEP_HOURS] = 2
    result = engine.assess(r)
    assert result.level is RiskLevel.ORANGE


def test_side_effects_is_yellow():
    r = _stable_responses()
    r[P.Q_SIDE_EFFECTS] = P.YES
    result = engine.assess(r)
    assert result.level is RiskLevel.YELLOW


def test_high_anxiety_is_yellow():
    r = _stable_responses()
    r[P.Q_ANXIETY] = 7
    result = engine.assess(r)
    assert result.level is RiskLevel.YELLOW


def test_conservative_combination_takes_highest():
    # Ansiedade elevada (amarelo) + crise (vermelho) => vermelho.
    r = _stable_responses()
    r[P.Q_ANXIETY] = 7
    r[P.Q_CRISIS] = P.YES
    result = engine.assess(r)
    assert result.level is RiskLevel.RED


def test_self_harm_forces_red_even_when_all_else_neutral():
    # CL-1: item estruturado e obrigatório de ideação/autoagressão. Todo o resto
    # neutro e SEM texto livre — antes disso seria VERDE (o único sinal de suicídio
    # vinha do texto livre, que é opcional). Agora "sim" aqui força VERMELHO.
    r = _stable_responses()
    r[P.Q_SELF_HARM] = P.YES
    result = engine.assess(r, free_text=None)
    assert result.level is RiskLevel.RED
    assert result.category_risks[P.CAT_RISCO] == RiskLevel.RED.value
    assert any("autoagress" in reason or "ideação" in reason for reason in result.reasons)


def test_self_harm_no_keeps_green():
    r = _stable_responses()
    r[P.Q_SELF_HARM] = P.NO
    result = engine.assess(r)
    assert result.level is RiskLevel.GREEN


def test_free_text_suicidal_forces_red():
    result = engine.assess(_stable_responses(), free_text="hoje eu não quero mais viver")
    assert result.level is RiskLevel.RED
    assert result.free_text_signals
    assert result.category_risks[P.CAT_LIVRE] == RiskLevel.RED.value


def test_unanalyzed_audio_escalates_green_to_yellow():
    # CL-2: check-in neutro, mas com áudio que não pôde ser transcrito/analisado.
    # Não pode virar VERDE em silêncio — sobe para AMARELO e pede revisão manual.
    result = engine.assess(_stable_responses(), free_text=None, audio_unanalyzed=True)
    assert result.level is RiskLevel.YELLOW
    assert any("áudio não analisado" in reason for reason in result.reasons)
    assert result.category_risks[P.CAT_LIVRE] == RiskLevel.YELLOW.value


def test_unanalyzed_audio_never_lowers_existing_risk():
    # O flag de áudio é um PISO (mínimo amarelo), nunca rebaixa um risco maior.
    r = _stable_responses()
    r[P.Q_CRISIS] = P.YES  # vermelho
    result = engine.assess(r, audio_unanalyzed=True)
    assert result.level is RiskLevel.RED


def test_boolean_true_is_treated_as_yes():
    r = _stable_responses()
    r[P.Q_CRISIS] = True
    assert engine.assess(r).level is RiskLevel.RED


def test_missing_responses_do_not_crash():
    result = engine.assess({})
    assert result.level is RiskLevel.GREEN
