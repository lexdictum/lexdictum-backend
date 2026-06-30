from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LexDictum API"
    app_env: str = "development"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]

    supabase_url: str = "https://your-project.supabase.co"
    supabase_anon_key: str = "dev-anon-key"
    supabase_service_role_key: str = "dev-service-role-key"
    supabase_jwt_secret: str = "dev-jwt-secret-change-in-production-min-32"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "case_document_chunks"

    redis_url: str = "redis://localhost:6379/0"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lexdictum"

    max_upload_size_bytes: int = 50 * 1024 * 1024
    allowed_upload_mime_types: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    ocr_enabled: bool = False
    tesseract_lang: str = "spa"
    otel_enabled: bool = False
    otel_exporter_endpoint: str | None = None
    signed_url_expires_seconds: int = 3600

    arq_max_tries: int = 3
    arq_retry_delay_seconds: int = 30

    embedding_model_name: str = "nlpaueb/legal-bert-base-uncased"
    embedding_provider: str = "local"
    embedding_service_url: str | None = None
    chunk_size: int = 512
    chunk_overlap: int = 64

    llm_provider: str = "openai"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"

    rag_top_k: int = 5
    rag_max_context_messages: int = 20
    rag_use_hybrid_search: bool = False
    rag_rrf_k: int = 60
    sentry_dsn: str | None = None
    rate_limit_chat_per_minute: int = 20
    rate_limit_enabled: bool = True

    rag_system_prompt: str = (
        "Eres LexDictum, un asistente jurídico especializado en derecho español. "
        "Responde en español claro y preciso, basándote únicamente en los fragmentos "
        "documentales proporcionados del expediente. Si la información no aparece en "
        "los documentos, indícalo explícitamente y no inventes hechos ni normativa. "
        "Cita las fuentes usando el formato [Fuente N] cuando te refieras a un "
        "fragmento concreto. Al final de tu respuesta, incluye un bloque JSON de "
        "citas con este formato exacto (sin markdown):\n"
        "<!--CITATIONS:[{\"source_index\":1,\"document_id\":\"...\","
        "\"page\":1,\"chunk_index\":0,\"text_snippet\":\"...\"}]-->"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_production(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.app_env == "production"


IMAGE_UPLOAD_MIME_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)


def effective_allowed_upload_mime_types(settings: Settings | None = None) -> frozenset[str]:
    settings = settings or get_settings()
    allowed = set(settings.allowed_upload_mime_types)
    if settings.ocr_enabled:
        allowed.update(IMAGE_UPLOAD_MIME_TYPES)
    return frozenset(allowed)
