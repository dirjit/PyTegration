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
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from pytegration.core.config import AppEnv, LLMProviderName, Settings
from pytegration.db.base import Base
from pytegration.main import create_app
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
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """A fresh in-memory database engine with all tables created.

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

    yield engine

    # Teardown: dispose the engine, discarding the in-memory database entirely.
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A single database session over the in-memory engine (for unit tests)."""
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(settings: Settings, db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """An HTTP client bound to a real app instance over the in-memory database.

    WHY drive the app through HTTP instead of calling functions? Integration
        tests exercise the FULL stack — routing, validation, dependency
        injection, error handling, and serialization — exactly as a real client
        would. httpx's ASGITransport calls the app in-process (no network, no
        port), so it is fast and reliable.
    JAVA NOTE: this is the role of Spring's MockMvc / WebTestClient.

    NOTE: ASGITransport does not run the app's lifespan, so we set the
        session_factory on app.state ourselves to point at the test database.
    """
    app = create_app(settings=settings)
    app.state.session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        # Every protected request needs the API key header; set it once as a
        # default so individual tests stay focused on behavior, not plumbing.
        http_client.headers["X-API-Key"] = settings.api_key
        yield http_client


@pytest_asyncio.fixture
async def task_service(db_session: AsyncSession) -> TaskService:
    """A TaskService wired to a repository over the in-memory session.

    SYNTAX TIP: fixtures can depend on other fixtures just by naming them as
        parameters. pytest builds the dependency graph for you — here
        `task_service` pulls in `db_session`, which pulls in the engine.
    """
    return TaskService(TaskRepository(db_session))
