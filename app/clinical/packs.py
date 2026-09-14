"""Pacotes clínicos por especialidade.

Um `ClinicalPack` reúne o que é específico de uma especialidade: as perguntas do
check-in (protocolo), as regras de risco, o catálogo de escalas disponíveis, a
categoria do texto livre e a mensagem de segurança. O resto do app (agenda,
financeiro, prontuário…) é agnóstico.

O registry resolve o pacote a partir de `doctor.specialty`, com **psiquiatria
como default** — então tenants existentes seguem idênticos. Novas especialidades
(psicologia, odontologia…) entram registrando um pacote aqui, sem tocar no motor.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field

from app.clinical.scales import SCALES, Scale
from app.models.enums import RiskLevel
from app.protocol import odontology as O
from app.protocol import psychiatry as P
from app.protocol.base import QuestionDef
from app.risk.engine import RiskThresholds, psychiatry_rules, psychology_rules
from app.risk.free_text import FreeTextAnalyzer, NullFreeTextAnalyzer
from app.risk.rules import ChoiceRule, NumericRule, Rule, RuleRiskEngine, YesRule


@dataclass(frozen=True)
class ClinicalPack:
    key: str                       # identificador do pacote (== specialty)
    label: str                     # nome exibível
    specialty: str                 # casa com Protocol.specialty / doctor.specialty
    protocol_name: str
    protocol_version: str
    protocol_description: str
    questions: tuple[QuestionDef, ...]          # seed do check-in
    scale_codes: tuple[str, ...]                # escalas do catálogo global disponíveis
    rules_factory: Callable[[RiskThresholds], list[Rule]]
    thresholds: RiskThresholds = field(default_factory=RiskThresholds)
    free_text_category: str = "Livre"
    protected_codes: frozenset[str] = frozenset()
    # Flags de produto que ligam/desligam módulos por especialidade.
    features: dict = field(default_factory=dict)
    safety_message: str | None = None
    # Se True, o texto/áudio livre passa pelo analisador de risco de saúde mental
    # (palavras de crise/CVV). Fora de saúde mental, desligar evita falso positivo.
    analyze_free_text: bool = True

    def category_map(self) -> dict[str, str]:
        return {q.code: q.category for q in self.questions}

    def build_engine(self, free_text_analyzer: FreeTextAnalyzer | None = None) -> RuleRiskEngine:
        analyzer = free_text_analyzer
        if not self.analyze_free_text:
            analyzer = NullFreeTextAnalyzer()  # ignora o analisador de saúde mental
        return RuleRiskEngine(
            rules=self.rules_factory(self.thresholds),
            category_map=self.category_map(),
            free_text_analyzer=analyzer,
            free_text_category=self.free_text_category,
        )

    def scales(self) -> list[Scale]:
        return [SCALES[c] for c in self.scale_codes if c in SCALES]

    def has_feature(self, name: str) -> bool:
        return bool(self.features.get(name, False))


_SAFETY_MENTAL_HEALTH = (
    "Se você está com pensamentos de se ferir ou de que não vale a pena viver, "
    "procure ajuda agora: ligue 188 (CVV, 24h) ou vá a uma emergência. "
    "Seu médico foi avisado."
)

PSYCHIATRY_PACK = ClinicalPack(
    key=P.PSYCHIATRY_SPECIALTY,
    label="Psiquiatria",
    specialty=P.PSYCHIATRY_SPECIALTY,
    protocol_name=P.PSYCHIATRY_PROTOCOL_NAME,
    protocol_version=P.PSYCHIATRY_PROTOCOL_VERSION,
    protocol_description="Protocolo diário de acompanhamento psiquiátrico (MVP).",
    questions=tuple(P.PSYCHIATRY_QUESTIONS),
    scale_codes=("phq9", "gad7"),
    rules_factory=psychiatry_rules,
    thresholds=RiskThresholds(),
    free_text_category=P.CAT_LIVRE,
    protected_codes=frozenset({P.Q_SELF_HARM, P.Q_CRISIS, P.Q_MEDICATION}),
    features={"medicacao": True, "wearables": True},
    safety_message=_SAFETY_MENTAL_HEALTH,
)

# --- Psicologia: reaproveita o acompanhamento de saúde mental, sem medicação ---
_PSY_SPECIALTY = "psicologia"
# Mesmas perguntas do check-in, exceto medicação e efeitos colaterais (o psicólogo
# não prescreve). Reindexa as posições para não deixar buracos.
_PSY_QUESTIONS = tuple(
    dataclasses.replace(q, position=i)
    for i, q in enumerate(
        (q for q in P.PSYCHIATRY_QUESTIONS if q.code not in {P.Q_MEDICATION, P.Q_SIDE_EFFECTS}),
        start=1,
    )
)

PSYCHOLOGY_PACK = ClinicalPack(
    key=_PSY_SPECIALTY,
    label="Psicologia",
    specialty=_PSY_SPECIALTY,
    protocol_name="Protocolo Psicológico — Acompanhamento diário",
    protocol_version="1.0",
    protocol_description="Protocolo diário de acompanhamento psicológico.",
    questions=_PSY_QUESTIONS,
    # Além de PHQ-9/GAD-7, o psicólogo tem estresse (PSS-10) e bem-estar (WHO-5).
    scale_codes=("phq9", "gad7", "pss10", "who5"),
    rules_factory=psychology_rules,
    thresholds=RiskThresholds(),
    free_text_category=P.CAT_LIVRE,
    protected_codes=frozenset({P.Q_SELF_HARM, P.Q_CRISIS}),
    features={"medicacao": False, "wearables": True},
    safety_message=_SAFETY_MENTAL_HEALTH,
)

# --- Odontologia: vertical fora de saúde mental (pós-procedimento) ---
_SAFETY_DENTAL = (
    "Em caso de sangramento intenso que não para, febre alta ou dor que piora, "
    "entre em contato com seu dentista ou procure um pronto-atendimento."
)


def odontology_rules(_t: RiskThresholds) -> list[Rule]:
    """Regras de risco odontológico (dor EVA, sangramento, febre, inchaço,
    adesão). Sem itens de saúde mental."""
    return [
        NumericRule(O.Q_PAIN, [
            (">=", 8, RiskLevel.RED, "dor intensa ({v:g}/10)"),
            (">=", 5, RiskLevel.ORANGE, "dor moderada ({v:g}/10)"),
            (">=", 3, RiskLevel.YELLOW, "dor leve ({v:g}/10)"),
        ]),
        YesRule(O.Q_BLEEDING, RiskLevel.RED, "sangramento relatado"),
        YesRule(O.Q_FEVER, RiskLevel.ORANGE, "febre relatada (possível infecção)"),
        ChoiceRule(O.Q_SWELLING, {
            O.SW_INTENSE: (RiskLevel.ORANGE, "inchaço intenso"),
            O.SW_MODERATE: (RiskLevel.YELLOW, "inchaço moderado"),
        }),
        ChoiceRule(O.Q_MEDICATION, {
            O.NO: (RiskLevel.YELLOW, "não tomou a medicação prescrita"),
        }),
    ]


ODONTOLOGY_PACK = ClinicalPack(
    key=O.ODONTOLOGY_SPECIALTY,
    label="Odontologia",
    specialty=O.ODONTOLOGY_SPECIALTY,
    protocol_name=O.ODONTOLOGY_PROTOCOL_NAME,
    protocol_version=O.ODONTOLOGY_PROTOCOL_VERSION,
    protocol_description="Acompanhamento odontológico pós-procedimento.",
    questions=tuple(O.ODONTOLOGY_QUESTIONS),
    scale_codes=(),  # sem escalas de saúde mental; a dor já é item do check-in
    rules_factory=odontology_rules,
    free_text_category=O.CAT_LIVRE,
    protected_codes=frozenset({O.Q_PAIN, O.Q_BLEEDING, O.Q_FEVER}),
    features={"medicacao": True, "wearables": False},
    safety_message=_SAFETY_DENTAL,
    analyze_free_text=False,  # palavras de crise/CVV não se aplicam à odontologia
)

# Registry por especialidade. Novas especialidades entram aqui.
CLINICAL_PACKS: dict[str, ClinicalPack] = {
    PSYCHIATRY_PACK.specialty: PSYCHIATRY_PACK,
    PSYCHOLOGY_PACK.specialty: PSYCHOLOGY_PACK,
    ODONTOLOGY_PACK.specialty: ODONTOLOGY_PACK,
}

DEFAULT_PACK = PSYCHIATRY_PACK


def get_pack(specialty: str | None) -> ClinicalPack:
    """Pacote da especialidade (case-insensitive); cai no default se não houver."""
    if not specialty:
        return DEFAULT_PACK
    return CLINICAL_PACKS.get(specialty.strip().lower(), DEFAULT_PACK)
