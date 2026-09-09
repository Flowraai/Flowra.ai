"""Provedores de dados de vestíveis — plugáveis e agnósticos de fabricante.

Contrato mínimo: iniciar a conexão do paciente (OAuth ou instantânea) e sincronizar
o resumo diário (sono, FC de repouso, HRV, passos). O `demo` gera dados sintéticos
plausíveis e roda sem credencial — faz o fluxo funcionar de ponta a ponta. Um
provedor real (Terra, Fitbit…) é registrar mais uma entrada em PROVIDERS e uma
classe implementando `begin_connect`/`sync`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Protocol

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.wearable import WearableConnection
    from app.models.patient import Patient


@dataclass(frozen=True)
class WearableProviderInfo:
    slug: str
    name: str
    description: str
    available: bool       # integração operante? (reais ficam pendentes até credencial/parceria)
    requires_oauth: bool  # paciente conecta a conta do fabricante (redireciona)?


PROVIDERS: dict[str, WearableProviderInfo] = {
    "demo": WearableProviderInfo(
        slug="demo",
        name="Demonstração",
        description=(
            "Gera dados de exemplo (sono, frequência cardíaca, HRV, passos) para "
            "demonstrar o acompanhamento por dispositivo. Sem conexão real."
        ),
        available=True,
        requires_oauth=False,
    ),
    "terra": WearableProviderInfo(
        slug="terra",
        name="Terra (Apple, Fitbit, Garmin, Samsung, Xiaomi…)",
        description=(
            "Agregador: o paciente conecta a marca do próprio dispositivo. Requer "
            "conta na Terra e credenciais no servidor."
        ),
        available=False,  # pronto para ligar quando as credenciais forem configuradas
        requires_oauth=True,
    ),
    "fitbit": WearableProviderInfo(
        slug="fitbit",
        name="Fitbit",
        description="Integração direta com Fitbit (OAuth). Requer app no dev.fitbit.com.",
        available=False,
        requires_oauth=True,
    ),
}


@dataclass(frozen=True)
class DailySample:
    day: date
    sleep_minutes: int | None = None
    resting_hr: int | None = None
    hrv_ms: int | None = None
    steps: int | None = None


class WearableProvider(Protocol):
    info: WearableProviderInfo

    async def begin_connect(self, patient: "Patient", connection: "WearableConnection") -> str | None:
        """Inicia a conexão. Retorna a URL de OAuth, ou None se já conecta na hora."""
        ...

    async def sync(
        self, patient: "Patient", connection: "WearableConnection", days: int
    ) -> list[DailySample]:
        """Busca o resumo diário dos últimos `days` dias."""
        ...


def _rng(seed_text: str) -> float:
    """Número determinístico em [0,1) a partir de um texto (estável entre execuções)."""
    h = hashlib.sha256(seed_text.encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class DemoProvider:
    """Dados sintéticos plausíveis (determinísticos por paciente+dia)."""

    info = PROVIDERS["demo"]

    async def begin_connect(self, patient: "Patient", connection: "WearableConnection") -> str | None:
        return None  # conecta instantaneamente (sem OAuth)

    async def sync(
        self, patient: "Patient", connection: "WearableConnection", days: int
    ) -> list[DailySample]:
        today = date.today()
        out: list[DailySample] = []
        for i in range(days):
            d = today - timedelta(days=i)
            base = f"{patient.id}:{d.isoformat()}"
            sleep = int(300 + _rng(base + ":sleep") * 200)       # 5h–8h20 (min)
            hr = int(56 + _rng(base + ":hr") * 26)               # 56–82 bpm
            hrv = int(22 + _rng(base + ":hrv") * 55)             # 22–77 ms
            steps = int(2000 + _rng(base + ":steps") * 11000)    # 2k–13k
            out.append(
                DailySample(day=d, sleep_minutes=sleep, resting_hr=hr, hrv_ms=hrv, steps=steps)
            )
        return out


def get_wearable_provider(slug: str | None = None) -> WearableProvider:
    """Provedor configurado (ou o demo). Provedores reais entram aqui quando ligados."""
    resolved = (slug or settings.wearable_provider or "demo").lower()
    # terra/fitbit ficam prontos para ligar: enquanto não operantes, cai no demo.
    if resolved in ("terra", "fitbit"):
        return DemoProvider()  # TODO: retornar TerraProvider/FitbitProvider quando habilitados
    return DemoProvider()


def active_provider_info() -> WearableProviderInfo:
    return PROVIDERS.get((settings.wearable_provider or "demo").lower(), PROVIDERS["demo"])
