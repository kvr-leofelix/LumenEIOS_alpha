import os
from typing import List
from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "LumenEIOS"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            if v.lower() in ("1", "true", "yes", "on", "dev", "development"):
                return True
            if v.lower() in ("0", "false", "no", "off", "release", "prod", "production"):
                return False
        return bool(v)
    SECRET_KEY: str = "lumeneios-super-secure-production-ready-secret-key-32charsmin!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Database configuration: defaults to SQLite+aiosqlite for zero-dependency local runs,
    # or PostgreSQL (postgresql+asyncpg://...) in Docker/Production
    DATABASE_URL: str = "sqlite+aiosqlite:///./lumeneios.db"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]

    # Object storage / MinIO
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "lumeneios-documents"
    STORAGE_LOCAL_DIR: str = "./storage_uploads"

    # OCR & ML Configuration
    OCR_CONFIDENCE_THRESHOLD: float = 0.85
    HF_TOKEN: str = ""
    DEFAULT_VISION_MODEL: str = "microsoft/trocr-base-handwritten"
    QWEN_VL_MODEL_ID: str = "Qwen/Qwen2.5-VL-3B-Instruct"

    # LLM Provider
    LLM_PROVIDER: str = "deterministic"  # "deterministic", "huggingface", "hosted"
    LLM_API_KEY: str = ""

    # Optional Neo4j Knowledge Graph
    NEO4J_ENABLED: bool = False
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # PayPal subscriptions. "sandbox" for testing, "live" for real money.
    PAYPAL_ENV: str = "sandbox"
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: SecretStr = SecretStr("")
    PAYPAL_WEBHOOK_ID: str = ""
    # Billing plans created once in PayPal: a flat school plan and a per-teacher seat plan.
    PAYPAL_BASE_PLAN_ID: str = ""
    PAYPAL_SEAT_PLAN_ID: str = ""
    # Where PayPal sends the principal after approving or cancelling checkout.
    PAYPAL_RETURN_URL: str = "http://localhost:3000/subscription/return"
    PAYPAL_CANCEL_URL: str = "http://localhost:3000/subscription/cancel"

    # Legacy demo mode allows anonymous requests to use the seeded admin.
    DEMO_MODE: bool = False
    # Enable the team root login explicitly in a development environment.
    DEMO_ROOT_PASSWORD: SecretStr | None = None

    @property
    def demo_root_enabled(self) -> bool:
        return self.APP_ENV == "development" and bool(
            self.DEMO_ROOT_PASSWORD and self.DEMO_ROOT_PASSWORD.get_secret_value()
        )


settings = Settings()
