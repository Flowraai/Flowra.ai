"""Configuração central da aplicação, carregada de variáveis de ambiente / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Aplicação
    app_name: str = "Flowra Care"
    environment: str = "development"
    debug: bool = True

    # Banco de dados
    database_url: str = "postgresql+asyncpg://flowra:flowra@localhost:5432/flowra_care"

    # Autenticação (perfil médico — JWT)
    jwt_secret_key: str = "troque-este-segredo-em-producao"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # Módulo de IA (análise do texto/áudio livre)
    free_text_analyzer: str = "keyword"  # keyword | llm
    # Endpoint compatível com a API OpenAI (chat completions). Funciona com
    # OpenAI, Azure OpenAI, Gemini (endpoint compat), Groq, OpenRouter, locais...
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 20

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Notificações ao médico (alertas)
    notification_channels: list[str] = Field(default_factory=lambda: ["log"])
    # SMTP (canal email)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True
    # Webhook (ponte para WhatsApp/push, etc.)
    notification_webhook_url: str | None = None

    @field_validator("cors_origins", "notification_channels", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
