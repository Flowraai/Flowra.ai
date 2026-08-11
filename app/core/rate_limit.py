"""Rate limiting (janela deslizante) para endpoints sensíveis.

Dois backends com a MESMA semântica (permite `max_attempts` na janela, rejeita o
próximo), escolhidos por `REDIS_URL`:
- em memória (default): estado por processo — ok para 1 worker (SEC-2).
- Redis (quando `REDIS_URL` setado): estado COMPARTILHADO e atômico entre
  múltiplos workers/instâncias — fecha o SEC-2 para escala horizontal.
Chaveado por IP do cliente (considera X-Forwarded-For, ver `_client_ip`).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger("flowra_care.rate_limit")


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Muitas tentativas. Tente novamente em instantes.",
        headers={"Retry-After": str(max(retry_after, 1))},
    )


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
            raise _too_many(int(self.window_seconds - (now - hits[0])) + 1)
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()

    @classmethod
    def reset_all(cls) -> None:
        for limiter in cls._registry:
            limiter.reset()


# Janela deslizante atômica no Redis (sorted set por chave). Retorna:
#   {0}              -> permitido
#   {1, oldest_ts}   -> rejeitado (timestamp do hit mais antigo, p/ Retry-After)
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= max then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  return {1, oldest[2]}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.ceil(window) + 1)
return {0}
"""


class RedisSlidingWindowRateLimiter:
    """Rate limit por janela deslizante COMPARTILHADO via Redis (SEC-2).

    Mesma semântica do SlidingWindowRateLimiter, mas consistente entre múltiplos
    workers/instâncias. A verificação é atômica (script Lua roda inteiro no Redis).
    Usa relógio de parede (time.time) — compartilhável, ao contrário do monotonic.
    Se o Redis estiver indisponível, falha ABERTO (libera) para não trancar o
    login numa queda do Redis; apenas registra o erro.
    """

    def __init__(self, max_attempts: int, window_seconds: int, redis_url: str) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._url = redis_url
        self._redis = None

    def _client(self):
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self._url, decode_responses=True)
        return self._redis

    async def check(self, key: str) -> None:
        now = time.time()
        member = f"{now:.6f}:{os.urandom(6).hex()}"
        try:
            result = await self._client().eval(
                _SLIDING_WINDOW_LUA, 1, key,
                str(now), str(self.window_seconds), str(self.max_attempts), member,
            )
        except Exception as exc:  # noqa: BLE001 — Redis fora não pode trancar o login
            logger.error("rate limit (Redis) indisponível, liberando: %s", exc)
            return
        if result and int(result[0]) == 1:
            oldest = float(result[1]) if len(result) > 1 and result[1] else now
            raise _too_many(int(self.window_seconds - (now - oldest)) + 1)


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
    """Fábrica de dependência FastAPI que limita por IP dentro de um escopo.

    Usa o backend Redis (compartilhado) quando `REDIS_URL` está setado; senão o de
    memória (por processo). A escolha é feita uma vez, no import das rotas.
    """
    if settings.redis_url:
        redis_limiter = RedisSlidingWindowRateLimiter(
            max_attempts, window_seconds, settings.redis_url
        )

        async def redis_dependency(request: Request) -> None:
            await redis_limiter.check(f"{scope}:{_client_ip(request)}")

        return redis_dependency

    mem_limiter = SlidingWindowRateLimiter(max_attempts, window_seconds)

    async def mem_dependency(request: Request) -> None:
        mem_limiter.check(f"{scope}:{_client_ip(request)}")

    return mem_dependency
