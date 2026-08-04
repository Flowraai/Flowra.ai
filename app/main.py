"""Ponto de entrada da API do Flowra Care."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import RequestContextMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger("flowra_care")

# Guardrails de produção: aborta em config insegura (JWT padrão, DEBUG) e
# registra avisos (ex.: criptografia em repouso desligada, DPA do LLM pendente).
for _warning in settings.enforce_production_guardrails():
    logger.warning("[produção] %s", _warning)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Backend do MVP de monitoramento psiquiátrico entre consultas. "
        "A IA não diagnostica: apoia a priorização de casos por risco."
    ),
    # Interface interativa e schema OpenAPI só fora de produção (superfície de ataque).
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Correlação/observabilidade por requisição (adicionado por último = executa primeiro).
app.add_middleware(RequestContextMiddleware)

app.include_router(api_router)


@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "name": settings.app_name,
        "status": "ok",
        "docs": "/docs" if settings.docs_enabled else None,
        "disclaimer": "Ferramenta de apoio à priorização — não substitui julgamento clínico.",
    }
