"""Escalas clínicas validadas (PHQ-9, GAD-7): definição, pontuação e gravidade.

Instrumentos de domínio público, amplamente usados em psiquiatria (measurement-
based care). A pontuação é a soma dos itens (0–3 cada); a faixa de gravidade e o
sinalizador de risco (ideação — item 9 do PHQ-9) são derivados aqui.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    min: int
    max: int
    label: str
    level: str  # green | yellow | orange | red (para a UI)


@dataclass(frozen=True)
class Scale:
    code: str
    name: str
    description: str
    period: str            # janela de referência mostrada ao paciente
    items: tuple[str, ...]
    options: tuple[str, ...]  # rótulos para 0,1,2,3
    bands: tuple[Band, ...]
    flag_item: int | None      # índice (0-based) que, se > 0, sinaliza risco
    flag_note: str | None

    @property
    def max_score(self) -> int:
        return len(self.items) * (len(self.options) - 1)


_OPTS = (
    "Nenhuma vez",
    "Vários dias",
    "Mais da metade dos dias",
    "Quase todos os dias",
)

PHQ9 = Scale(
    code="phq9",
    name="PHQ-9 — Depressão",
    description="Rastreio e monitoramento de sintomas depressivos (últimas 2 semanas).",
    period="Nas últimas 2 semanas, com que frequência você foi incomodado(a) por…",
    items=(
        "Pouco interesse ou pouco prazer em fazer as coisas",
        "Se sentir para baixo, deprimido(a) ou sem perspectiva",
        "Dificuldade para pegar no sono, continuar dormindo ou dormir demais",
        "Se sentir cansado(a) ou com pouca energia",
        "Falta de apetite ou comer demais",
        "Se sentir mal consigo mesmo(a) — ou achar que é um fracasso ou que decepcionou você mesmo(a) ou sua família",
        "Dificuldade para se concentrar (ler jornal, ver televisão)",
        "Lentidão para se mover ou falar (a ponto de outras pessoas notarem) — ou o oposto, muito agitado(a) ou inquieto(a)",
        "Pensar em se ferir de alguma maneira ou que seria melhor estar morto(a)",
    ),
    options=_OPTS,
    bands=(
        Band(0, 4, "Mínima", "green"),
        Band(5, 9, "Leve", "yellow"),
        Band(10, 14, "Moderada", "orange"),
        Band(15, 19, "Moderadamente grave", "red"),
        Band(20, 27, "Grave", "red"),
    ),
    flag_item=8,  # item 9 (ideação)
    flag_note="Item 9 (pensamentos de morte/autoagressão) positivo",
)

GAD7 = Scale(
    code="gad7",
    name="GAD-7 — Ansiedade",
    description="Rastreio e monitoramento de sintomas de ansiedade (últimas 2 semanas).",
    period="Nas últimas 2 semanas, com que frequência você foi incomodado(a) por…",
    items=(
        "Se sentir nervoso(a), ansioso(a) ou muito tenso(a)",
        "Não conseguir parar ou controlar as preocupações",
        "Preocupar-se demais com diferentes coisas",
        "Dificuldade para relaxar",
        "Ficar tão agitado(a) que se torna difícil permanecer parado(a)",
        "Ficar facilmente aborrecido(a) ou irritado(a)",
        "Sentir medo como se algo terrível fosse acontecer",
    ),
    options=_OPTS,
    bands=(
        Band(0, 4, "Mínima", "green"),
        Band(5, 9, "Leve", "yellow"),
        Band(10, 14, "Moderada", "orange"),
        Band(15, 21, "Grave", "red"),
    ),
    flag_item=None,
    flag_note=None,
)

SCALES: dict[str, Scale] = {s.code: s for s in (PHQ9, GAD7)}


def get_scale(code: str) -> Scale | None:
    return SCALES.get(code)


def band_for(scale: Scale, score: int) -> Band:
    for b in scale.bands:
        if b.min <= score <= b.max:
            return b
    return scale.bands[-1]


def score_scale(code: str, answers: list[int]) -> tuple[int, str, str, bool]:
    """Valida e pontua. Retorna (score, severity_label, level, flagged).

    Levanta ValueError se o código for inválido ou as respostas não baterem.
    """
    scale = get_scale(code)
    if scale is None:
        raise ValueError(f"Escala desconhecida: {code!r}")
    if len(answers) != len(scale.items):
        raise ValueError(
            f"Esperado {len(scale.items)} respostas, recebido {len(answers)}."
        )
    hi = len(scale.options) - 1
    for a in answers:
        if not isinstance(a, int) or a < 0 or a > hi:
            raise ValueError(f"Resposta fora do intervalo 0–{hi}: {a!r}")
    total = sum(answers)
    band = band_for(scale, total)
    flagged = scale.flag_item is not None and answers[scale.flag_item] > 0
    return total, band.label, band.level, flagged
