from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite:///./evalforge.db"

    # Redis (optional for MVP)
    redis_url: str | None = None

    # LLM API Keys
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # API Settings
    api_title: str = "EvalForge API"
    api_version: str = "1.0.0"
    api_description: str = "LLM Evaluation & Benchmarking Platform"

    # CORS - can be comma-separated string or list
    cors_origins: str | list[str] = "http://localhost:3000"

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
