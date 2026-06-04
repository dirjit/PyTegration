"""Integration tests for API-key authentication.

LESSON: Module 8 (Security). See docs/08-security.md
"""

from __future__ import annotations

from httpx import AsyncClient

TASKS = "/api/v1/tasks"


async def test_protected_route_requires_a_key(client: AsyncClient) -> None:
    """Without the API-key header, a protected route returns 401."""
    # The fixture sets a default key; remove it to simulate an anonymous caller.
    client.headers.pop("X-API-Key", None)

    response = await client.get(TASKS)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_protected_route_rejects_a_wrong_key(client: AsyncClient) -> None:
    """A present-but-incorrect key is also rejected with 401."""
    response = await client.get(TASKS, headers={"X-API-Key": "not-the-real-key"})
    assert response.status_code == 401


async def test_protected_route_accepts_the_correct_key(client: AsyncClient) -> None:
    """With the correct key (set by the fixture), the request succeeds."""
    response = await client.get(TASKS)
    assert response.status_code == 200


async def test_health_is_open_without_a_key(client: AsyncClient) -> None:
    """SECURITY: health probes must remain unauthenticated."""
    client.headers.pop("X-API-Key", None)
    response = await client.get("/health")
    assert response.status_code == 200


async def test_response_carries_a_request_id_header(client: AsyncClient) -> None:
    """Observability: every response echoes an X-Request-ID for correlation."""
    response = await client.get("/health")
    assert response.headers.get("X-Request-ID")
