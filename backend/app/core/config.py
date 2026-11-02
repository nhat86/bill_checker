from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "dev-secret-change-me-in-production-32bytes"
    access_token_expire_minutes: int = 60 * 24 * 7

    database_url: str = "postgresql+psycopg://billchecker:billchecker@localhost:5433/billchecker"
    redis_url: str = "redis://localhost:6379/0"

    # Storage: "minio" (S3-compatible) or "fs" (local filesystem)
    storage_backend: str = "fs"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "bill-checker"
    local_storage_dir: str = "./data/uploads"

    groq_api_key: str = ""
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    # "groq" for real OCR, "fixture" for offline dev (returns canned receipt)
    ocr_backend: str = "groq"

    frontend_origin: str = "http://localhost:3000"

    max_upload_mb: int = 20


settings = Settings()
