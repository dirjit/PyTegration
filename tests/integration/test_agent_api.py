"""Integration test for the agent endpoint, end to end, fully offline.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md

The `client` fixture uses LLM_PROVIDER=mock, so this exercises the entire agent
stack — route, loop, tools, and the real TaskService over the in-memory DB —
without any network or API key.
"""

from __future__ import annotations

from httpx import AsyncClient

AGENT = "/api/v1/agent/chat"
TASKS = "/api/v1/tasks"


async def test_agent_requires_auth(client: AsyncClient) -> None:
    """The agent endpoint inherits the router-level API-key protection."""
    client.headers.pop("X-API-Key", None)
    response = await client.post(AGENT, json={"message": "hi"})
    assert response.status_code == 401


async def test_agent_creates_then_summarizes(client: AsyncClient) -> None:
    """A multi-step request creates a task and reports a summary, with a trace."""
    response = await client.post(
        AGENT,
        json={"message": "create a high priority task to deploy, then summarize my open tasks"},
    )
    assert response.status_code == 200
    body = response.json()

    # The agent took multiple steps and exposed an auditable trace.
    assert body["iterations"] >= 2
    tools_used = [t["tool"] for t in body["trace"]]
    assert "create_task" in tools_used
    assert "summarize_tasks" in tools_used
    assert all(t["ok"] for t in body["trace"])
    assert body["reply"]

    # The side effect really happened: a task now exists via the normal API.
    listing = (await client.get(TASKS)).json()
    assert listing["total"] == 1
    assert listing["items"][0]["priority"] == "high"


async def test_agent_validates_input(client: AsyncClient) -> None:
    """An empty message is rejected by the request schema (422)."""
    response = await client.post(AGENT, json={"message": ""})
    assert response.status_code == 422
