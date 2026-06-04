"""Integration test for the token-bucket rate limiter.

LESSON: Module 8 (Security). See docs/08-security.md
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from pytegration.core.config import AppEnv, LLMProviderName, Settings
from pytegration.main import create_app


@pytest_asyncio.fixture
async def tiny_limit_client(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """A client whose app allows a burst of just ONE request per window.

    WHY a separate fixture? We override only the rate-limit settings here so the
        other tests keep a generous limit and stay fast/isolated.
    """
    settings = Settings(
        app_env=AppEnv.TEST,
        api_key="test-key",
        llm_provider=LLMProviderName.MOCK,
        rate_limit_capacity=1,
        rate_limit_window_seconds=60,
    )
    app = create_app(settings=settings)
    app.state.session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.headers["X-API-Key"] = settings.api_key
        yield client


async def test_second_request_is_rate_limited(tiny_limit_client: AsyncClient) -> None:
    """With capacity=1, the first request passes and the second gets 429."""
    first = await tiny_limit_client.get("/api/v1/tasks")
    assert first.status_code == 200

    second = await tiny_limit_client.get("/api/v1/tasks")
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"
    assert second.headers.get("Retry-After")
