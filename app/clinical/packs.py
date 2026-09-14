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

from collections.abc import Callable
from dataclasses import dataclass, field

from app.clinical.scales import SCALES, Scale
from app.protocol import psychiatry as P
from app.protocol.psychiatry import QuestionDef
from app.risk.engine import RiskThresholds, psychiatry_rules
from app.risk.free_text import FreeTextAnalyzer
from app.risk.rules import Rule, RuleRiskEngine


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

    def category_map(self) -> dict[str, str]:
        return {q.code: q.category for q in self.questions}

    def build_engine(self, free_text_analyzer: FreeTextAnalyzer | None = None) -> RuleRiskEngine:
        return RuleRiskEngine(
            rules=self.rules_factory(self.thresholds),
            category_map=self.category_map(),
            free_text_analyzer=free_text_analyzer,
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

# Registry por especialidade. Novas especialidades entram aqui.
CLINICAL_PACKS: dict[str, ClinicalPack] = {
    PSYCHIATRY_PACK.specialty: PSYCHIATRY_PACK,
}

DEFAULT_PACK = PSYCHIATRY_PACK


def get_pack(specialty: str | None) -> ClinicalPack:
    """Pacote da especialidade (case-insensitive); cai no default se não houver."""
    if not specialty:
        return DEFAULT_PACK
    return CLINICAL_PACKS.get(specialty.strip().lower(), DEFAULT_PACK)
