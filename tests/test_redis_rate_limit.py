"""SEC-2 — rate limiter compartilhado via Redis. Pula se não houver Redis."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.rate_limit import RedisSlidingWindowRateLimiter

REDIS_URL = "redis://localhost:6379/0"


async def _redis_reachable() -> bool:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        return True
    except Exception:
        return False


async def test_blocks_after_max_attempts():
    if not await _redis_reachable():
        pytest.skip("Redis indisponível — defina o serviço redis para este teste.")
    limiter = RedisSlidingWindowRateLimiter(3, 60, REDIS_URL)
    key = f"test:{uuid.uuid4()}"
    for _ in range(3):
        await limiter.check(key)  # as 3 primeiras passam
    with pytest.raises(HTTPException) as exc:
        await limiter.check(key)  # a 4ª é barrada
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


async def test_state_is_shared_across_instances():
    # Duas instâncias (== dois workers) compartilham o balde via Redis.
    if not await _redis_reachable():
        pytest.skip("Redis indisponível.")
    key = f"test:{uuid.uuid4()}"
    worker_a = RedisSlidingWindowRateLimiter(2, 60, REDIS_URL)
    worker_b = RedisSlidingWindowRateLimiter(2, 60, REDIS_URL)
    await worker_a.check(key)
    await worker_b.check(key)  # 2º hit por OUTRA instância
    with pytest.raises(HTTPException):
        await worker_a.check(key)  # 3º barrado — o estado é compartilhado


async def test_fails_open_when_redis_down():
    # Redis inalcançável não pode trancar o login: libera (fail-open), sem levantar.
    limiter = RedisSlidingWindowRateLimiter(1, 60, "redis://127.0.0.1:6390/0")
    await limiter.check("qualquer")  # não levanta, mesmo sem Redis
    await limiter.check("qualquer")
