"""Provedores de dados de vestíveis — plugáveis e agnósticos de fabricante.

Contrato mínimo: iniciar a conexão do paciente (OAuth ou instantânea) e sincronizar
o resumo diário (sono, FC de repouso, HRV, passos). O `demo` gera dados sintéticos
plausíveis e roda sem credencial — faz o fluxo funcionar de ponta a ponta. Um
provedor real (Terra, Fitbit…) é registrar mais uma entrada em PROVIDERS e uma
classe implementando `begin_connect`/`sync`.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol

import httpx

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.wearable import WearableConnection
    from app.models.patient import Patient

logger = logging.getLogger("flowra_care.wearable")


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


def terra_configured() -> bool:
    return bool(settings.terra_api_key and settings.terra_dev_id)


# ---- Terra (agregador: Xiaomi, Samsung, Apple, Garmin, Fitbit…) ----
_TERRA_BASE = "https://api.tryterra.co/v2"


def _terra_headers() -> dict[str, str]:
    return {
        "dev-id": settings.terra_dev_id or "",
        "x-api-key": settings.terra_api_key or "",
        "Content-Type": "application/json",
    }


def _dig(d: Any, *path: str) -> Any:
    """Navega d[a][b][c] com segurança (retorna None se faltar)."""
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _as_date(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def _to_int(v: Any) -> int | None:
    try:
        return int(round(float(v))) if v is not None else None
    except (TypeError, ValueError):
        return None


def map_terra_records(daily: list[dict], sleep: list[dict]) -> dict[date, DailySample]:
    """Converte payloads /daily e /sleep da Terra em resumos por dia."""
    out: dict[date, DailySample] = {}

    for rec in daily or []:
        d = _as_date(_dig(rec, "metadata", "start_time")) or _as_date(_dig(rec, "metadata", "end_time"))
        if d is None:
            continue
        sample = out.get(d) or DailySample(day=d)
        out[d] = replace(
            sample,
            resting_hr=_to_int(_dig(rec, "heart_rate_data", "summary", "resting_hr_bpm")),
            hrv_ms=_to_int(
                _dig(rec, "heart_rate_data", "summary", "avg_hrv_rmssd")
                or _dig(rec, "heart_rate_data", "summary", "avg_hrv_sdnn")
            ),
            steps=_to_int(_dig(rec, "distance_data", "steps")),
        )

    for rec in sleep or []:
        d = _as_date(_dig(rec, "metadata", "end_time")) or _as_date(_dig(rec, "metadata", "start_time"))
        if d is None:
            continue
        secs = _dig(rec, "sleep_durations_data", "asleep", "duration_asleep_state_seconds")
        minutes = _to_int(secs / 60) if isinstance(secs, (int, float)) else None
        sample = out.get(d) or DailySample(day=d)
        out[d] = replace(sample, sleep_minutes=minutes)

    return out


class TerraProvider:
    """Agregador Terra. O paciente conecta a marca dele pelo widget (OAuth)."""

    info = PROVIDERS["terra"]

    async def begin_connect(self, patient: "Patient", connection: "WearableConnection") -> str | None:
        """Gera a sessão do widget e devolve a URL para o paciente autorizar."""
        body: dict[str, Any] = {
            "reference_id": str(patient.id),
            "language": "pt",
        }
        if settings.terra_providers:
            body["providers"] = settings.terra_providers
        if settings.patient_app_url_base:
            body["auth_success_redirect_url"] = settings.patient_app_url_base
            body["auth_failure_redirect_url"] = settings.patient_app_url_base
        async with httpx.AsyncClient(timeout=20, headers=_terra_headers()) as http:
            resp = await http.post(f"{_TERRA_BASE}/auth/generateWidgetSession", json=body)
            resp.raise_for_status()
            return resp.json().get("url")

    async def _pull(self, path: str, user_id: str, days: int) -> list[dict]:
        end = date.today()
        start = end - timedelta(days=days)
        params = {
            "user_id": user_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "to_webhook": "false",
        }
        async with httpx.AsyncClient(timeout=30, headers=_terra_headers()) as http:
            resp = await http.get(f"{_TERRA_BASE}/{path}", params=params)
            resp.raise_for_status()
            return resp.json().get("data", []) or []

    async def sync(
        self, patient: "Patient", connection: "WearableConnection", days: int
    ) -> list[DailySample]:
        user_id = connection.external_user_id
        if not user_id:
            return []  # ainda não autorizou pelo widget (webhook define o user_id)
        try:
            daily = await self._pull("daily", user_id, days)
            sleep = await self._pull("sleep", user_id, days)
        except httpx.HTTPError as exc:
            logger.warning("Falha ao buscar dados na Terra (paciente=%s): %s", patient.id, exc)
            return []
        return list(map_terra_records(daily, sleep).values())


def get_wearable_provider(slug: str | None = None) -> WearableProvider:
    """Provedor configurado (ou o demo se o real não estiver com credenciais)."""
    resolved = (slug or settings.wearable_provider or "demo").lower()
    if resolved == "terra" and terra_configured():
        return TerraProvider()
    # fitbit e demais ficam prontos para ligar; sem credencial, cai no demo.
    return DemoProvider()


def active_provider_info() -> WearableProviderInfo:
    slug = (settings.wearable_provider or "demo").lower()
    info = PROVIDERS.get(slug, PROVIDERS["demo"])
    # Reflete o estado real: só "disponível" quando as credenciais existem.
    if slug == "terra":
        return replace(info, available=terra_configured())
    return info
