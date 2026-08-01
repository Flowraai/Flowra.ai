"""Provedores de emissão de receita (plugáveis).

A emissão com **valor legal** (assinatura ICP-Brasil, regras de controlado —
Portaria 344/98) é responsabilidade de uma **plataforma certificada**. Aqui só
definimos o contrato e delegamos:

- `internal` (default): registra a receita e gera uma referência interna, **SEM
  valor legal**. Serve para o fluxo do MVP/testes.
- `certified`: integra a plataforma certificada (ex.: Memed/Nexodata) via API.
  Requer credenciais (PRESCRIPTION_API_BASE_URL / PRESCRIPTION_API_KEY).

Contrato: `issue(prescription) -> (external_id, pdf_url)`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.prescription import Prescription


class PrescriptionProvider(Protocol):
    legal_value: bool

    async def issue(self, prescription: "Prescription") -> tuple[str, str | None]:
        """Emite a receita e retorna (external_id, pdf_url)."""
        ...


class InternalPrescriptionProvider:
    """Registro interno — SEM valor legal. Para MVP/testes."""

    legal_value = False

    async def issue(self, prescription: "Prescription") -> tuple[str, str | None]:
        return f"internal:{prescription.id}", None


class CertifiedPrescriptionProvider:
    """Integração com plataforma certificada (ICP-Brasil / controlado).

    Placeholder: implementa o contrato, mas exige credenciais. A chamada real à
    API do parceiro entra em `issue` quando o provedor for definido.
    """

    legal_value = True

    async def issue(self, prescription: "Prescription") -> tuple[str, str | None]:
        if not (settings.prescription_api_base_url and settings.prescription_api_key):
            raise RuntimeError(
                "Provedor de receita certificado não configurado "
                "(defina PRESCRIPTION_API_BASE_URL e PRESCRIPTION_API_KEY)."
            )
        # TODO: POST à API do parceiro (cria a prescrição, dispara assinatura
        # ICP-Brasil) e mapear a resposta para (external_id, pdf_url).
        raise NotImplementedError("Integração com a plataforma certificada pendente.")


def get_prescription_provider() -> PrescriptionProvider:
    if settings.prescription_provider == "certified":
        return CertifiedPrescriptionProvider()
    return InternalPrescriptionProvider()
