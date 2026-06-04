"""Shared pytest fixtures for the whole test suite.

LESSON: Module 7 (Testing). See docs/07-testing.md

WHAT IS conftest.py?
    A special file pytest discovers automatically. Fixtures defined here are
    available to every test in this directory tree WITHOUT importing them.
    JAVA NOTE: think of fixtures as JUnit `@BeforeEach` setup combined with
    dependency injection — but composable and explicitly requested by name in
    each test's parameter list (e.g. `def test_x(task_service): ...`).

WHY an in-memory SQLite database for tests?
    It is created fresh per test, needs no server, and runs in milliseconds — so
    the suite is fast and isolated. The async session pattern is identical to the
    real Postgres-or-file-SQLite setup, so the tests exercise real SQL.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from pytegration.core.config import AppEnv, LLMProviderName, Settings
from pytegration.db.base import Base
from pytegration.repositories.task_repository import TaskRepository
from pytegration.services.task_service import TaskService


@pytest.fixture
def settings() -> Settings:
    """Test settings: a known API key and the offline mock provider.

    SYNTAX TIP: `@pytest.fixture` registers a factory. A test that lists
        `settings` as a parameter receives whatever this function returns.
    """
    return Settings(
        app_env=AppEnv.TEST,
        api_key="test-key",
        llm_provider=LLMProviderName.MOCK,
        cors_origins="http://testserver",
    )


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Provide a clean in-memory database session for one test.

    WHY StaticPool + a single in-memory connection? A `:memory:` SQLite database
        lives inside ONE connection; StaticPool reuses that single connection so
        the schema we create is visible to every query in the test.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables directly from the ORM metadata (fast path for tests).
    # Production uses Alembic migrations; tests don't need migration history.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    # Teardown: dispose the engine, discarding the in-memory database entirely.
    await engine.dispose()


@pytest_asyncio.fixture
async def task_service(db_session: AsyncSession) -> TaskService:
    """A TaskService wired to a repository over the in-memory session.

    SYNTAX TIP: fixtures can depend on other fixtures just by naming them as
        parameters. pytest builds the dependency graph for you — here
        `task_service` pulls in `db_session`, which pulls in the engine.
    """
    return TaskService(TaskRepository(db_session))
