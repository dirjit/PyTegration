"""Agent tools — the SAFE, fixed set of actions the LLM may request.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
LAYER:  agent

SECURITY — this file is the agent's security boundary. Three rules:
    1. ALLOW-LIST: the model can only call tools defined in `TOOLS` below. There
       is no "run arbitrary code/SQL" tool. Anything outside the list is refused.
    2. RE-VALIDATE: the model's argument JSON is UNTRUSTED input. Every call's
       arguments are parsed through a Pydantic model before execution, so bad or
       malicious payloads are rejected exactly like a hostile HTTP request.
    3. SAME AUTHORITY: every tool delegates to the SAME TaskService the REST API
       uses. The agent therefore cannot do anything a normal API client couldn't.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from pytegration.agent.provider import ToolResult, ToolSpec
from pytegration.domain.enums import TaskPriority, TaskStatus
from pytegration.schemas.task import TaskCreate, TaskUpdate
from pytegration.services.task_service import TaskService

# SYNTAX TIP: `Callable[[A, B], Awaitable[R]]` is the type of an async function
#   taking (A, B) and returning R. It is how you type "a coroutine function" —
#   the rough analog of a `Function`/`BiFunction` functional interface in Java.
ToolHandler = Callable[[TaskService, BaseModel], Awaitable[dict[str, Any]]]


# =============================================================================
# Argument models — one Pydantic model per tool. These do double duty:
#   (a) generate the JSON Schema advertised to the model, and
#   (b) validate the model's argument JSON before we execute anything.
# Keeping ONE definition for both guarantees the schema and the validation match.
# =============================================================================


class _CreateTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200, description="Short task title.")
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)


class _ListTasksArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TaskStatus | None = Field(default=None, description="Optional status filter.")
    limit: int = Field(default=20, ge=1, le=100)


class _UpdateStatusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: int = Field(ge=1, description="Id of the task to update.")
    status: TaskStatus = Field(description="New status for the task.")


class _SummarizeArgs(BaseModel):
    # No inputs; modeled explicitly so every tool has a schema.
    model_config = ConfigDict(extra="forbid")


# =============================================================================
# Handlers — each delegates to TaskService and returns a JSON-able dict.
# =============================================================================


async def _create_task(service: TaskService, args: BaseModel) -> dict[str, Any]:
    # SYNTAX TIP: `cast` is a TYPE-ONLY hint — it tells mypy "trust me, this is a
    #   _CreateTaskArgs" without any runtime check or cost. The registry guarantees
    #   the right model was validated for this handler, so the cast is safe.
    create = cast(_CreateTaskArgs, args)
    created = await service.create_task(
        TaskCreate(title=create.title, description=create.description, priority=create.priority)
    )
    return {"id": created.id, "title": created.title, "status": created.status.value}


async def _list_tasks(service: TaskService, args: BaseModel) -> dict[str, Any]:
    query = cast(_ListTasksArgs, args)
    items, total = await service.list_tasks(status=query.status, limit=query.limit)
    return {
        "total": total,
        "tasks": [
            {"id": t.id, "title": t.title, "status": t.status.value, "priority": t.priority.value}
            for t in items
        ],
    }


async def _update_status(service: TaskService, args: BaseModel) -> dict[str, Any]:
    update = cast(_UpdateStatusArgs, args)
    updated = await service.update_task(update.task_id, TaskUpdate(status=update.status))
    return {"id": updated.id, "status": updated.status.value}


async def _summarize(service: TaskService, args: BaseModel) -> dict[str, Any]:
    return await service.summarize_tasks()


@dataclass(frozen=True)
class Tool:
    """A registered tool: its advertised spec, its arg model, and its handler."""

    name: str
    description: str
    args_model: type[BaseModel]
    handler: ToolHandler

    def spec(self) -> ToolSpec:
        """Build the provider-facing spec, deriving JSON Schema from the model.

        WHY derive the schema from the Pydantic model? One source of truth: the
            exact shape we validate against is the exact shape we tell the model
            about. They can never drift apart.
        """
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.args_model.model_json_schema(),
        )


# THE ALLOW-LIST. To add a capability, add an entry here — nothing else can run.
TOOLS: dict[str, Tool] = {
    "create_task": Tool(
        name="create_task",
        description="Create a new task with a title and optional description/priority.",
        args_model=_CreateTaskArgs,
        handler=_create_task,
    ),
    "list_tasks": Tool(
        name="list_tasks",
        description="List existing tasks, optionally filtered by status.",
        args_model=_ListTasksArgs,
        handler=_list_tasks,
    ),
    "update_task_status": Tool(
        name="update_task_status",
        description="Change the status of an existing task (todo, in_progress, done).",
        args_model=_UpdateStatusArgs,
        handler=_update_status,
    ),
    "summarize_tasks": Tool(
        name="summarize_tasks",
        description="Return counts of tasks by status, including how many are open.",
        args_model=_SummarizeArgs,
        handler=_summarize,
    ),
}


def tool_specs() -> list[ToolSpec]:
    """All tool specs to advertise to the model."""
    return [tool.spec() for tool in TOOLS.values()]


async def dispatch_tool_call(
    *, service: TaskService, call_id: str, name: str, arguments: dict[str, Any]
) -> ToolResult:
    """Validate and execute one tool call, returning a result for the model.

    SECURITY: this function is the single choke point where untrusted model
        output becomes an action. It (1) checks the allow-list, (2) validates the
        arguments, and only then (3) runs the handler. Any failure is returned as
        an `is_error` result so the model can recover — we never crash the loop.
    """
    tool = TOOLS.get(name)
    if tool is None:
        # The model asked for a tool that does not exist (or is not allowed).
        return ToolResult(call_id=call_id, content=f"Unknown tool: {name!r}", is_error=True)

    try:
        # Re-validate the untrusted arguments against the tool's Pydantic model.
        validated = tool.args_model.model_validate(arguments)
    except Exception as exc:
        # WHY catch broad `Exception`? We deliberately turn ANY validation failure
        #   into a tool error the model can read and recover from — a bad tool call
        #   must never crash the agent loop.
        return ToolResult(call_id=call_id, content=f"Invalid arguments: {exc}", is_error=True)

    result = await tool.handler(service, validated)
    # `json.dumps` serializes the result; the model reads this text as the output.
    return ToolResult(call_id=call_id, content=json.dumps(result))
