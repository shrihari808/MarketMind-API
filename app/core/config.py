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
    LLM_TEMPERATURE: float = Field(default=0.2, description="Default temperature for LLM generation")
    EMBEDDING_BATCH_SIZE: int = Field(default=32, description="Batch size for generating embeddings")

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
    MAX_SEARCH_RESULTS: int = Field(default=7, description="Maximum search results retrieved per query")
    MAX_SCRAPED_SOURCES: int = 5
    SCRAPER_TIMEOUT_SECONDS: int = 8
    RAG_CHUNK_SIZE: int = Field(default=400, description="Word chunk size for document passages")
    RAG_CHUNK_OVERLAP: int = Field(default=50, description="Overlap between consecutive passage chunks")
    
    # Search Engine API Keys
    SERPER_API_KEY: Optional[str] = Field(default=None, description="Serper.dev API Key")
    BRAVE_API_KEY: Optional[str] = Field(default=None, description="Brave Search API Key")
    TAVILY_API_KEY: Optional[str] = Field(default=None, description="Tavily API Key")

    # Vector Store
    CHROMA_PERSIST_DIRECTORY: str = "./data/chroma"

    # Market Dashboard Configuration
    DASHBOARD_ENABLED: bool = Field(default=True, description="Enable or disable market dashboard services")
    DASHBOARD_CACHE_TTL_HOURS: float = Field(default=1.0, description="Dashboard cache TTL in hours (e.g. 0.25, 1.0, 4.0)")

    # Deep Equity Research Configuration
    RESEARCH_SECTION_BY_SECTION: bool = Field(
        default=False,
        description="Generate equity report section-by-section via modular prompts (True) or cohesive single-pass (False)"
    )

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable or disable IP rate limiting")
    RATE_LIMIT_PER_MINUTE: int = Field(default=25, description="Maximum allowed requests per minute per IP")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns cached settings instance with zero side-effects on import."""
    return Settings()
