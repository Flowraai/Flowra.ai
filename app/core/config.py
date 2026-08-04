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
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    password_reset_expire_minutes: int = 30
    # Base do link de redefinição de senha (painel). Se vazio, envia só o token.
    password_reset_url_base: str | None = None

    # Rate limiting (janela deslizante em memória) dos endpoints sensíveis
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 60
    register_rate_limit_attempts: int = 10
    password_reset_rate_limit_attempts: int = 5

    # Risco por tendência e não-adesão
    risk_trend_window: int = 5          # nº de check-ins recentes considerados
    inactivity_alert_days: int = 2      # dias sem check-in que disparam alerta
    medication_missed_alert_streak: int = 3  # faltas seguidas que disparam alerta
    appointment_reminder_hours: int = 24     # antecedência do lembrete de consulta

    # Receita: provedor de emissão. internal (registro sem valor legal, default) |
    # certified (plataforma certificada com ICP-Brasil — requer credenciais).
    prescription_provider: str = "internal"
    prescription_api_base_url: str | None = None
    prescription_api_key: str | None = None

    # Anexos (fotos/arquivos/áudio) — armazenamento plugável
    # local (default, disco) | ... (produção troca por object storage/S3)
    storage_backend: str = "local"
    storage_dir: str = "./var/uploads"
    upload_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    upload_allowed_types: list[str] = Field(
        default_factory=lambda: [
            "image/jpeg", "image/png", "image/webp", "application/pdf",
            "audio/mpeg", "audio/mp4", "audio/aac", "audio/ogg", "audio/webm", "audio/wav",
        ]
    )

    # Transcrição de áudio (check-in por voz): none (default) | openai (Whisper-compat)
    transcription_provider: str = "none"
    transcription_base_url: str = "https://api.openai.com/v1"
    transcription_api_key: str | None = None
    transcription_model: str = "whisper-1"

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

    # Onboarding do paciente (link do app/PWA enviado ao contato do paciente)
    patient_app_url_base: str | None = None

    # Notificações ao médico (alertas)
    notification_channels: list[str] = Field(default_factory=lambda: ["log"])
    # SMTP (canal email)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True
    # Webhook (ponte genérica)
    notification_webhook_url: str | None = None
    # Push (app): log (default, dev) | expo (Expo Push, RN/Expo)
    push_provider: str = "log"
    expo_access_token: str | None = None  # opcional (Expo)
    # WhatsApp (Meta Cloud API)
    whatsapp_phone_number_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_api_version: str = "v21.0"
    whatsapp_template_name: str | None = None  # obrigatório fora da janela de 24h
    whatsapp_template_lang: str = "pt_BR"

    @field_validator("cors_origins", "notification_channels", "upload_allowed_types", mode="before")
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
