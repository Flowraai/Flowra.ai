"""Rate limiting simples (janela deslizante em memória) para endpoints sensíveis.

MVP: estado em processo — suficiente para uma instância. Para múltiplas
instâncias/workers, trocar por um backend compartilhado (ex.: Redis) mantendo a
mesma interface. Chaveado por IP do cliente (considera X-Forwarded-For).
"""

from __future__ import annotations

import ipaddress
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowRateLimiter:
    # Registro de todas as instâncias, para reset em testes.
    _registry: list["SlidingWindowRateLimiter"] = []

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        SlidingWindowRateLimiter._registry.append(self)

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_attempts:
            retry_after = int(self.window_seconds - (now - hits[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Tente novamente em instantes.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()

    @classmethod
    def reset_all(cls) -> None:
        for limiter in cls._registry:
            limiter.reset()


def _is_trusted_proxy(ip: str) -> bool:
    """Proxy confiável = loopback ou rede privada. Nesta implantação a API só é
    alcançável pelo proxy (rede interna do Docker), então só esses IPs podem ter
    populado o X-Forwarded-For legitimamente."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private


def _client_ip(request: Request) -> str:
    """IP real do cliente para o rate limit.

    SEC-1 — o X-Forwarded-For só é considerado quando o peer imediato é um proxy
    confiável; senão um cliente externo poderia forjar o header e zerar o balde a
    cada request (brute-force livre). Quando confiável, caminhamos o XFF da direita
    para a esquerda ignorando IPs de proxies confiáveis: o primeiro IP não-confiável
    é o cliente real (defende contra entradas prependidas/forjadas)."""
    peer = request.client.host if request.client else "unknown"
    if settings.rate_limit_trust_forwarded_for and _is_trusted_proxy(peer):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            for hop in reversed(hops):
                if not _is_trusted_proxy(hop):
                    return hop
    return peer


def rate_limit(
    max_attempts: int, window_seconds: int, scope: str
) -> Callable[[Request], Awaitable[None]]:
    """Fábrica de dependência FastAPI que limita por IP dentro de um escopo."""
    limiter = SlidingWindowRateLimiter(max_attempts, window_seconds)

    async def dependency(request: Request) -> None:
        limiter.check(f"{scope}:{_client_ip(request)}")

    return dependency
