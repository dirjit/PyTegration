"""Unit tests for the generic Toolbox and Nova's read-only guide tools.

LESSON: Module 11 (Cosmic Explorer). See docs/11-cosmic-explorer.md
"""

from __future__ import annotations

import json

from pytegration.agent.guide_tools import GUIDE_TOOLS, guide_toolbox
from pytegration.agent.tools import dispatch_tool_call
from pytegration.repositories.cosmos_catalog import CosmosCatalog
from pytegration.services.cosmos_service import CosmosService
from pytegration.services.task_service import TaskService


async def test_domain_error_in_a_tool_is_contained(task_service: TaskService) -> None:
    """v0.1 BUG FIX: updating a missing task used to abort the whole agent run.

    Now the NotFoundError comes back as a tool error the model can recover from.
    """
    result = await dispatch_tool_call(
        service=task_service,
        call_id="c1",
        name="update_task_status",
        arguments={"task_id": 999, "status": "done"},
    )
    assert result.is_error
    assert "not found" in result.content.lower()


def test_guide_tools_are_all_read_only_by_name() -> None:
    """A cheap tripwire: no Nova tool may sound like it changes anything."""
    for name in GUIDE_TOOLS:
        assert not any(verb in name for verb in ("create", "update", "delete", "set_", "write"))


async def test_guide_lookup_returns_a_summary() -> None:
    toolbox = guide_toolbox(CosmosService(CosmosCatalog()))
    result = await toolbox.dispatch(
        call_id="g1", name="lookup_object", arguments={"name": "Saturn"}
    )
    assert not result.is_error
    assert json.loads(result.content)["summary"].startswith("🪐 Saturn")


async def test_guide_rejects_unbounded_arguments() -> None:
    toolbox = guide_toolbox(CosmosService(CosmosCatalog()))
    result = await toolbox.dispatch(
        call_id="g2", name="weight_on_world", arguments={"name": "mars", "earth_weight": 10_000}
    )
    assert result.is_error and "Invalid arguments" in result.content
