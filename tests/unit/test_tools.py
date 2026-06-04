"""Unit tests for agent tools — the security boundary.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md

These tests assert the three security rules from tools.py hold: allow-list,
argument re-validation, and delegation to the real service.
"""

from __future__ import annotations

import json

from pytegration.agent.tools import dispatch_tool_call, tool_specs
from pytegration.services.task_service import TaskService


def test_tool_specs_are_well_formed() -> None:
    """Every advertised tool has a name, description, and a JSON-Schema object."""
    specs = tool_specs()
    names = {s.name for s in specs}
    assert {"create_task", "list_tasks", "update_task_status", "summarize_tasks"} <= names
    for spec in specs:
        assert spec.description
        assert spec.input_schema["type"] == "object"  # valid JSON Schema root


async def test_unknown_tool_is_refused(task_service: TaskService) -> None:
    """ALLOW-LIST: a tool not in the registry returns an error, never executes."""
    result = await dispatch_tool_call(
        service=task_service, call_id="c1", name="rm_rf", arguments={}
    )
    assert result.is_error
    assert "Unknown tool" in result.content


async def test_invalid_arguments_are_rejected(task_service: TaskService) -> None:
    """RE-VALIDATE: bad arguments (blank title) become a recoverable tool error."""
    result = await dispatch_tool_call(
        service=task_service, call_id="c2", name="create_task", arguments={"title": ""}
    )
    assert result.is_error
    assert "Invalid arguments" in result.content


async def test_extra_arguments_are_rejected(task_service: TaskService) -> None:
    """RE-VALIDATE: unexpected fields (extra=forbid) are refused — no injection."""
    result = await dispatch_tool_call(
        service=task_service,
        call_id="c3",
        name="create_task",
        arguments={"title": "ok", "danger": "rm -rf"},
    )
    assert result.is_error


async def test_create_task_tool_actually_creates(task_service: TaskService) -> None:
    """DELEGATION: a valid call runs through the real TaskService and persists."""
    result = await dispatch_tool_call(
        service=task_service,
        call_id="c4",
        name="create_task",
        arguments={"title": "Ship", "priority": "high"},
    )
    assert not result.is_error
    payload = json.loads(result.content)
    assert payload["title"] == "Ship"

    # The task is really in the database now.
    fetched = await task_service.get_task(payload["id"])
    assert fetched.title == "Ship"
