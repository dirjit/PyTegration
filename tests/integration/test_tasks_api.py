"""Integration tests for the Task CRUD API (full HTTP stack).

LESSON: Module 7 (Testing). See docs/07-testing.md

These tests drive the API exactly as a client would, validating routing,
request/response schemas, status codes, and error mapping end to end.
"""

from __future__ import annotations

from httpx import AsyncClient

BASE = "/api/v1/tasks"


async def test_create_task_returns_201_and_body(client: AsyncClient) -> None:
    """POST creates a task, returns 201, and echoes server-managed fields."""
    response = await client.post(BASE, json={"title": "Ship it", "priority": "high"})

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["title"] == "Ship it"
    assert body["priority"] == "high"
    assert body["status"] == "todo"  # the server sets the initial status


async def test_create_rejects_unknown_fields(client: AsyncClient) -> None:
    """SECURITY: extra=forbid blocks mass-assignment of unexpected fields."""
    response = await client.post(
        BASE,
        json={"title": "x", "is_admin": True},  # is_admin is not a task field
    )
    assert response.status_code == 422


async def test_create_rejects_blank_title(client: AsyncClient) -> None:
    """Validation: an empty title violates min_length and is rejected."""
    response = await client.post(BASE, json={"title": ""})
    assert response.status_code == 422


async def test_get_missing_task_returns_404_envelope(client: AsyncClient) -> None:
    """A missing task yields the standard error envelope with code 'not_found'."""
    response = await client.get(f"{BASE}/424242")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert "424242" in body["error"]["message"]


async def test_list_paginates_and_filters(client: AsyncClient) -> None:
    """Listing returns a Page envelope and honors the status filter."""
    await client.post(BASE, json={"title": "a"})
    second = (await client.post(BASE, json={"title": "b"})).json()
    # Move the second task to DONE.
    await client.patch(f"{BASE}/{second['id']}", json={"status": "done"})

    page = (await client.get(BASE)).json()
    assert page["total"] == 2
    assert page["limit"] == 20 and page["offset"] == 0
    assert len(page["items"]) == 2

    done = (await client.get(BASE, params={"status": "done"})).json()
    assert done["total"] == 1
    assert done["items"][0]["title"] == "b"


async def test_update_then_delete_lifecycle(client: AsyncClient) -> None:
    """PATCH updates a field; DELETE removes the task (204), then GET is 404."""
    created = (await client.post(BASE, json={"title": "temp"})).json()
    task_id = created["id"]

    patched = await client.patch(f"{BASE}/{task_id}", json={"status": "in_progress"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "in_progress"

    deleted = await client.delete(f"{BASE}/{task_id}")
    assert deleted.status_code == 204

    assert (await client.get(f"{BASE}/{task_id}")).status_code == 404


async def test_invalid_status_filter_is_rejected(client: AsyncClient) -> None:
    """An out-of-enum status query value fails validation (422)."""
    response = await client.get(BASE, params={"status": "nonsense"})
    assert response.status_code == 422
