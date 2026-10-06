"""
Shared Pytest Fixtures and Lifecycle Management.
Ensures clean database connection lifecycle and provides isolated mock clients.
"""

import pytest
import pytest_asyncio
from app.core.database import init_db, close_db, engine, Base


@pytest_asyncio.fixture(scope="session", autouse=True)
async def manage_test_db():
    """Initializes tables before tests run and disposes engine connection pool on shutdown."""
    await init_db()
    yield
    await close_db()
