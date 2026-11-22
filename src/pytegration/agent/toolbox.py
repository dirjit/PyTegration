"""Toolbox — a generic, reusable allow-list of tools bound to a context object.

LESSON: Module 11 (Cosmic Explorer) builds on Module 10. See docs/11-cosmic-explorer.md
LAYER:  agent

WHY was this extracted in v0.2?
    v0.1 had ONE agent (the task assistant) whose tools all took a TaskService.
    v0.2 adds a second agent — Nova, the kids' Space Guide — whose tools take a
    CosmosService. Rather than copy the dispatch/validation code, we made it
    GENERIC over the "context" the tools act on. The agent loop now just asks a
    toolbox for its specs and to dispatch calls; it never knows which agent it is.

SYNTAX TIP: `TypeVar` + `Generic[ContextT]` declare a generic class, so
    `Toolbox[TaskService]` and `Toolbox[CosmosService]` are distinct, type-checked
    types. JAVA NOTE: exactly `class Toolbox<C> { ... }`.

SECURITY: the three rules from tools.py still hold, now in ONE place for every
    agent: allow-list, re-validate untrusted arguments, and (new) contain
    failures — a handler raising a domain error becomes a tool error the model
    can read and recover from, instead of aborting the whole conversation.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from pytegration.agent.provider import ToolResult, ToolSpec
from pytegration.core.errors import AppError

ContextT = TypeVar("ContextT")


@dataclass(frozen=True)
class Tool(Generic[ContextT]):
    """A registered tool: its advertised spec, its arg model, and its handler."""

    name: str
    description: str
    args_model: type[BaseModel]
    # SYNTAX TIP: `Callable[[A, B], Awaitable[R]]` is the type of an async
    #   function taking (A, B) and returning R — here, (context, validated args).
    handler: Callable[[ContextT, BaseModel], Awaitable[dict[str, Any]]]

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


class Toolbox(Generic[ContextT]):
    """An allow-list of tools plus the context they act on (one per request)."""

    def __init__(self, context: ContextT, tools: Mapping[str, Tool[ContextT]]) -> None:
        self._context = context
        self._tools = tools

    def specs(self) -> list[ToolSpec]:
        """All tool specs to advertise to the model."""
        return [tool.spec() for tool in self._tools.values()]

    async def dispatch(self, *, call_id: str, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Validate and execute one tool call, returning a result for the model.

        SECURITY: the single choke point where untrusted model output becomes an
            action: (1) allow-list, (2) validate, (3) run, (4) contain failures.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(call_id=call_id, content=f"Unknown tool: {name!r}", is_error=True)

        try:
            validated = tool.args_model.model_validate(arguments)
        except PydanticValidationError as exc:
            return ToolResult(call_id=call_id, content=f"Invalid arguments: {exc}", is_error=True)

        try:
            result = await tool.handler(self._context, validated)
        except AppError as exc:
            # v0.1 BUG FIX: a handler raising e.g. NotFoundError used to escape the
            #   loop and turn the whole chat into a 404. An EXPECTED domain error
            #   is information the model can act on ("no task 42 — let me list
            #   them"), so we hand it back as a tool error. Unexpected exceptions
            #   still propagate to the global handler (a bug should be loud).
            return ToolResult(call_id=call_id, content=exc.message, is_error=True)

        return ToolResult(call_id=call_id, content=json.dumps(result))
