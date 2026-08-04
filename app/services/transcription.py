"""Transcrição de áudio (check-in por voz), plugável.

Padrão `none` (não transcreve — o áudio fica salvo como anexo). Com
`TRANSCRIPTION_PROVIDER=openai`, usa um endpoint compatível com a API OpenAI
(`/audio/transcriptions`, modelo Whisper-compat). Qualquer erro/ausência de chave
retorna None — o check-in segue normalmente, só sem o texto do áudio.
"""

from __future__ import annotations

import httpx

from app.core.config import settings


async def transcribe(data: bytes, content_type: str, filename: str = "audio") -> str | None:
    provider = settings.transcription_provider.lower()
    if provider == "none" or not settings.transcription_api_key:
        return None
    if provider != "openai":
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as http:
            resp = await http.post(
                f"{settings.transcription_base_url.rstrip('/')}/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.transcription_api_key}"},
                data={"model": settings.transcription_model},
                files={"file": (filename, data, content_type)},
            )
            resp.raise_for_status()
            text = resp.json().get("text")
            return text.strip() if isinstance(text, str) and text.strip() else None
    except Exception:  # noqa: BLE001 — falha de transcrição não bloqueia o check-in
        return None
