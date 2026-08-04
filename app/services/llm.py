"""Cliente LLM assíncrono (endpoint compatível com a API OpenAI).

Reaproveita a mesma configuração do analisador de texto livre (LLM_BASE_URL /
LLM_API_KEY / LLM_MODEL). Retorna None se não houver chave ou em qualquer erro —
o chamador decide o fallback.
"""

from __future__ import annotations

import httpx

from app.core.config import settings


async def chat_complete(system: str, user: str, temperature: float = 0.2) -> str | None:
    # Guardrail LGPD: sem chave, ou em produção sem DPA reconhecido, não envia
    # contexto clínico ao provedor externo.
    if not settings.llm_available:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as http:
            resp = await http.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:  # noqa: BLE001 — falha do LLM cai no fallback do chamador
        return None
