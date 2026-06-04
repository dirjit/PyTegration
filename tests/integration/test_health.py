"""Integration tests for the health endpoints.

LESSON: Module 7 (Testing). See docs/07-testing.md
"""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_is_ok(client: AsyncClient) -> None:
    """/health returns 200 with a status payload."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_ready_is_ok(client: AsyncClient) -> None:
    """/ready returns 200."""
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
