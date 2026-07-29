"""Risco por tendência — detecta "padrão de piora" ao longo dos check-ins.

Complementa o risco pontual (de um único check-in) olhando a janela recente:
piora sustentada, humor caindo, ansiedade subindo e não-adesão repetida. É
conservador e determinístico; a combinação final (feita no checkin_service)
mantém o MAIOR risco entre o pontual e o de tendência.

Função pura (sem DB), portanto testável. Recebe os check-ins recentes já
ordenados do mais recente para o mais antigo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import RiskLevel
from app.protocol import psychiatry as P


@dataclass
class CheckInPoint:
    """Visão mínima de um check-in para a análise de tendência."""

    level: RiskLevel
    responses: dict


@dataclass
class TrendThresholds:
    sustained_count: int = 3          # nº de check-ins seguidos em risco (>= amarelo)
    declining_moods: int = 3          # nº de leituras de humor em queda estrita
    nonadherence_window: int = 3      # janela para checar não-adesão
    nonadherence_count: int = 2       # nº de não-adesões na janela que preocupa


@dataclass
class TrendAssessment:
    level: RiskLevel = RiskLevel.GREEN
    reasons: list[str] = field(default_factory=list)


def _to_number(value: object) -> float | None:
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


def _choice(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip().lower()
    return None


def assess_trend(
    points: list[CheckInPoint], thresholds: TrendThresholds | None = None
) -> TrendAssessment:
    """`points[0]` é o check-in mais recente."""
    t = thresholds or TrendThresholds()
    result = TrendAssessment()

    if len(points) < 2:
        return result  # sem histórico suficiente para falar de tendência

    def escalate(level: RiskLevel, reason: str) -> None:
        result.level = result.level.escalate(level)
        result.reasons.append(reason)

    # 1. Piora sustentada: N check-ins seguidos (a partir do mais recente) em risco.
    streak = 0
    for point in points:
        if point.level.order >= RiskLevel.YELLOW.order:
            streak += 1
        else:
            break
    if streak >= t.sustained_count:
        escalate(RiskLevel.ORANGE, f"risco elevado sustentado ({streak} check-ins seguidos)")

    # 2. Humor em queda estrita nas últimas leituras disponíveis.
    moods = [m for m in (_to_number(p.responses.get(P.Q_MOOD)) for p in points) if m is not None]
    recent_moods = moods[: t.declining_moods]  # mais recente -> mais antigo
    if len(recent_moods) >= t.declining_moods and all(
        recent_moods[i] < recent_moods[i + 1] for i in range(len(recent_moods) - 1)
    ):
        escalate(
            RiskLevel.ORANGE,
            f"humor em queda nos últimos {len(recent_moods)} check-ins",
        )

    # 3. Não-adesão repetida à medicação na janela recente.
    window = points[: t.nonadherence_window]
    nonadherent = sum(
        1
        for p in window
        if _choice(p.responses.get(P.Q_MEDICATION)) in (P.NO, P.PARTIAL)
    )
    if nonadherent >= t.nonadherence_count:
        escalate(
            RiskLevel.ORANGE,
            f"não-adesão à medicação em {nonadherent} dos últimos {len(window)} check-ins",
        )

    return result
