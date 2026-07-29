"""Rate limiting simples (janela deslizante em memória) para endpoints sensíveis.

MVP: estado em processo — suficiente para uma instância. Para múltiplas
instâncias/workers, trocar por um backend compartilhado (ex.: Redis) mantendo a
mesma interface. Chaveado por IP do cliente (considera X-Forwarded-For).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status


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


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(
    max_attempts: int, window_seconds: int, scope: str
) -> Callable[[Request], Awaitable[None]]:
    """Fábrica de dependência FastAPI que limita por IP dentro de um escopo."""
    limiter = SlidingWindowRateLimiter(max_attempts, window_seconds)

    async def dependency(request: Request) -> None:
        limiter.check(f"{scope}:{_client_ip(request)}")

    return dependency
