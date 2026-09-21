"""
Asynchronous Database Layer.
Supports serverless PostgreSQL (Neon.tech / Supabase) via asyncpg with
automatic local SQLite fallback for offline development.
"""

import os
from typing import AsyncGenerator
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, Integer, DateTime
from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()

# Default to local SQLite if DATABASE_URL is not set
DATABASE_URL = settings.DATABASE_URL
if not DATABASE_URL:
    os.makedirs("./data", exist_ok=True)
    DATABASE_URL = "sqlite+aiosqlite:///./data/marketmind.db"
    logger.info("DATABASE_URL not set. Falling back to local SQLite: ./data/marketmind.db")

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
    """Persistent storage for multi-turn user/AI chat conversations."""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, nullable=True)
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully.")
