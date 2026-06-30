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
        "image/jpeg",
        "image/png",
        "image/webp",
    ]
    signed_url_expires_seconds: int = 3600

    arq_max_tries: int = 3
    arq_retry_delay_seconds: int = 30

    embedding_model_name: str = "nlpaueb/legal-bert-base-uncased"
    chunk_size: int = 512
    chunk_overlap: int = 64


@lru_cache
def get_settings() -> Settings:
    return Settings()
