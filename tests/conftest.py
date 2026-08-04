"""Fixtures de teste.

Os testes de integração precisam de um Postgres alcançável via DATABASE_URL.
Quando não houver banco, eles são **pulados** (skip) — os testes de unidade
(motor de risco, texto livre, smoke da API) continuam rodando sem banco.
"""

from __future__ import annotations

import os
import tempfile

# Isola os uploads dos testes num diretório temporário (antes de importar a app,
# pois as settings são lidas na importação).
os.environ.setdefault("STORAGE_DIR", tempfile.mkdtemp(prefix="flowra-test-uploads-"))

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.rate_limit import SlidingWindowRateLimiter
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.scripts.seed_protocol import seed_psychiatry_protocol


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Zera o estado dos rate limiters em memória entre os testes."""
    SlidingWindowRateLimiter.reset_all()
    yield
    SlidingWindowRateLimiter.reset_all()

# Tabelas com dados mutáveis, limpas entre cada teste (protocolos permanecem).
# device_tokens e tenants não têm FK que casque a partir das demais, então entram
# explicitamente; o CASCADE cuida das tabelas filhas (checkins, medicação, etc.).
_MUTABLE_TABLES = [
    "alerts", "checkins", "audit_logs", "device_tokens", "attachments",
    "patients", "doctors", "users", "tenants",
]


async def _db_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def client() -> httpx.AsyncClient:
    """Cliente HTTP contra a app, com banco limpo e protocolo populado.

    Pula o teste se não houver Postgres disponível.
    """
    # O pytest-asyncio usa um event loop por teste; o pool do engine async fica
    # preso ao loop anterior. Descartar o pool força conexões novas no loop atual.
    await engine.dispose()

    if not await _db_reachable():
        pytest.skip(
            "Postgres indisponível — defina DATABASE_URL para rodar os testes de integração."
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await session.execute(text(f"TRUNCATE {', '.join(_MUTABLE_TABLES)} CASCADE"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await seed_psychiatry_protocol(session)
        await session.commit()

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            yield http_client
    finally:
        await engine.dispose()
