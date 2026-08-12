"""Provedores de emissão de receita — plugáveis e **por médico**.

Cada médico escolhe uma plataforma e conecta a **própria conta** (o token fica
cifrado em repouso). A receita com **valor legal** (assinatura ICP-Brasil, regras
de controlado — Portaria 344/98) é responsabilidade da plataforma certificada;
aqui definimos o contrato e delegamos.

Provedores registrados:
- `none` (default): apenas **registra** a receita no sistema, **sem valor legal**
  (histórico/rascunho). Roda sem credencial.
- `memed`: emissão com assinatura digital e envio ao paciente. Exige conta na
  Memed e a credencial de integração. Deixado **pronto para ligar** — a chamada
  real é habilitada quando a parceria/homologação estiver concluída.

Adicionar um novo provedor (Nexodata, iClinic Rx, Receita Digital…) é registrar
mais uma entrada em `PROVIDERS` e uma classe implementando `issue`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.models.doctor import Doctor
    from app.models.prescription import Prescription


@dataclass(frozen=True)
class ProviderInfo:
    slug: str
    name: str
    legal_value: bool          # emite documento com valor legal?
    requires_credential: bool  # precisa que o médico conecte uma conta/token?
    credential_label: str | None
    description: str
    available: bool            # integração já operante? (memed fica pendente até a parceria)


PROVIDERS: dict[str, ProviderInfo] = {
    "none": ProviderInfo(
        slug="none",
        name="Registro interno (sem valor legal)",
        legal_value=False,
        requires_credential=False,
        credential_label=None,
        description=(
            "Apenas registra a receita no sistema, sem assinatura digital. "
            "Use como histórico/rascunho — não vale como receita na farmácia."
        ),
        available=True,
    ),
    "memed": ProviderInfo(
        slug="memed",
        name="Memed",
        legal_value=True,
        requires_credential=True,
        credential_label="Token de integração Memed",
        description=(
            "Emissão com assinatura digital (ICP-Brasil), incluindo controlados, "
            "e envio ao paciente. Requer conta na Memed e a credencial de integração."
        ),
        available=False,  # pronto para ligar quando a parceria/homologação concluir
    ),
}

DEFAULT_PROVIDER = "none"


class PrescriptionProvider(Protocol):
    info: ProviderInfo

    async def issue(self, prescription: "Prescription") -> tuple[str, str | None]:
        """Emite a receita e retorna (external_id, pdf_url)."""
        ...


class NoneProvider:
    """Registro interno — SEM valor legal. Fallback e uso para histórico."""

    info = PROVIDERS["none"]

    async def issue(self, prescription: "Prescription") -> tuple[str, str | None]:
        return f"internal:{prescription.id}", None


class MemedProvider:
    """Integração Memed — pronta para ligar.

    A emissão real (assinatura + envio) é habilitada quando a parceria estiver
    concluída e a chamada à API/SDK da Memed for plugada em `issue`.
    """

    info = PROVIDERS["memed"]

    def __init__(self, credential: str | None) -> None:
        self._credential = credential

    async def issue(self, prescription: "Prescription") -> tuple[str, str | None]:
        if not self._credential:
            raise RuntimeError(
                "Conecte sua conta Memed nas Configurações antes de emitir."
            )
        # TODO: chamar a API/SDK da Memed (criar prescrição, assinar, enviar) e
        # mapear a resposta para (external_id, pdf_url).
        raise NotImplementedError(
            "Integração Memed pendente de homologação/parceria. A conta já pode ser "
            "conectada; a emissão é habilitada assim que a integração for concluída."
        )


def get_prescription_provider(doctor: "Doctor") -> PrescriptionProvider:
    """Provedor configurado para este médico (ou o padrão sem valor legal)."""
    slug = (doctor.prescription_provider or DEFAULT_PROVIDER).lower()
    if slug == "memed":
        return MemedProvider(doctor.prescription_credential)
    return NoneProvider()
