"""
Asynchronous Database Layer.
Supports serverless PostgreSQL (Neon.tech / Supabase) via asyncpg with
automatic local SQLite fallback for offline development.
"""

import os
from typing import AsyncGenerator, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, Integer, DateTime
from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()

def _normalize_database_url(url: Optional[str]) -> str:
    """
    Normalizes database connection string for Async SQLAlchemy and asyncpg.
    Filters out libpq-specific parameters (like channel_binding and sslmode)
    that cause asyncpg connection errors, and enforces SSL for cloud hosts (Neon, Supabase).
    """
    if not url:
        os.makedirs("./data", exist_ok=True)
        logger.info("DATABASE_URL not set. Falling back to local SQLite: ./data/marketmind.db")
        return "sqlite+aiosqlite:///./data/marketmind.db"

    clean = url.strip()
    if "sqlite" in clean:
        return clean

    from sqlalchemy.engine.url import make_url

    try:
        parsed = make_url(clean)
        query_dict = dict(parsed.query)

        # Check if SSL is required by query string or known cloud hostnames
        host = (parsed.host or "").lower()
        needs_ssl = (
            "sslmode" in query_dict
            or "ssl" in query_dict
            or "channel_binding" in query_dict
            or "neon.tech" in host
            or "supabase" in host
        )

        # asyncpg accepts strictly 'ssl' (not 'sslmode' or 'channel_binding')
        new_query = {}
        if needs_ssl:
            new_query["ssl"] = "require"

        if "statement_cache_size" in query_dict:
            new_query["statement_cache_size"] = query_dict["statement_cache_size"]

        normalized = parsed.set(drivername="postgresql+asyncpg", query=new_query)
        final_url = normalized.render_as_string(hide_password=False)
        logger.info(f"Database URL normalized for asyncpg (host={parsed.host}, ssl={new_query.get('ssl')})")
        return final_url
    except Exception as e:
        logger.warning(f"Error normalizing database URL ({e}). Using raw string with asyncpg prefix.")
        if clean.startswith("postgresql://"):
            clean = "postgresql+asyncpg://" + clean[len("postgresql://"):]
        clean = clean.replace("sslmode=", "ssl=")
        return clean

DATABASE_URL = _normalize_database_url(settings.DATABASE_URL)

# Create Async Engine
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True
)

# Async Session Factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base declarative class for all database models."""
    pass


class ChatMessageRecord(Base):
    """
    Persistent storage for multi-turn user/AI chat conversations,
    isolated by anonymous browser client UUID (client_id) and session_id.
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="default_client")
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DashboardCacheRecord(Base):
    """Cached market snapshots supporting Stale-While-Revalidate without background daemons."""
    __tablename__ = "dashboard_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initializes database tables on startup if they do not exist."""
    import asyncio
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Connecting to database and initializing schema (attempt {attempt}/{max_retries})...")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables initialized successfully.")
            return
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Database connection attempt {attempt} failed ({e}). Retrying in 2 seconds...")
                await asyncio.sleep(2)
            else:
                logger.error(f"Database initialization failed after {max_retries} attempts: {e}")
                raise


async def close_db():
    """Disposes database connection engine on shutdown."""
    await engine.dispose()
    logger.info("Database connection engine disposed.")
