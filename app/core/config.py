"""
Application Configuration Module.
Type-safe configuration using Pydantic Settings with zero import-time side-effects.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings."""

    # Project metadata
    APP_NAME: str = "MarketMind-API"
    VERSION: str = "2.0.0"
    ENVIRONMENT: str = Field(default="development", description="development | production | staging")
    DEBUG: bool = Field(default=False)
    API_V1_PREFIX: str = "/api/v1"

    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.vercel.app"
    ]

    # API Security
    REQUIRE_API_KEY: bool = Field(default=False)
    API_KEY: Optional[str] = Field(default=None)

    # Google Gemini Configuration
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google AI Studio Gemini API Key")
    GEMINI_MODEL: str = Field(default="gemini-2.0-flash", description="Default model for synthesis")
    GEMINI_EMBEDDING_MODEL: str = Field(default="text-embedding-004", description="Default embedding model")

    # Database Configuration (Serverless PostgreSQL: Neon / Supabase)
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Async PostgreSQL connection string (postgresql+asyncpg://...)"
    )

    # Search & Scraping Parameters
    SEARCH_PROVIDER: str = Field(
        default="duckduckgo",
        description="Search provider to use: 'duckduckgo', 'serper', or 'brave'"
    )
    DEFAULT_COUNTRY: str = "IN"
    MAX_SEARCH_RESULTS: int = 7
    MAX_SCRAPED_SOURCES: int = 5
    SCRAPER_TIMEOUT_SECONDS: int = 8
    
    # Search Engine API Keys
    SERPER_API_KEY: Optional[str] = Field(default=None, description="Serper.dev API Key")
    BRAVE_API_KEY: Optional[str] = Field(default=None, description="Brave Search API Key")
    TAVILY_API_KEY: Optional[str] = Field(default=None, description="Tavily API Key")

    # Vector Store
    CHROMA_PERSIST_DIRECTORY: str = "./data/chroma"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns cached settings instance with zero side-effects on import."""
    return Settings()
