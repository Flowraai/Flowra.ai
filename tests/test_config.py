"""Parsing das settings a partir de variáveis de ambiente."""

from __future__ import annotations

from app.core.config import Settings


def test_csv_env_vars_parse_as_list(monkeypatch):
    # Os campos de lista (CORS_ORIGINS, NOTIFICATION_CHANNELS, ...) são CSV no .env.
    # Sem `NoDecode`, o pydantic-settings tentava decodificar como JSON primeiro e
    # quebrava o boot com um CSV — obrigando o workaround de JSON no .env da VPS.
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com,https://b.com")
    monkeypatch.setenv("NOTIFICATION_CHANNELS", "log,email")
    monkeypatch.setenv("ADMIN_EMAILS", "A@X.com, b@x.com")

    s = Settings()

    assert s.cors_origins == ["https://a.com", "https://b.com"]
    assert s.notification_channels == ["log", "email"]
    assert s.admin_emails == ["a@x.com", "b@x.com"]  # normalizados p/ minúsculo


def test_list_defaults_when_env_absent(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("NOTIFICATION_CHANNELS", raising=False)
    s = Settings()
    assert s.cors_origins == ["http://localhost:3000"]
    assert s.notification_channels == ["log"]
