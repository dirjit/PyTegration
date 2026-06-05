"""tools.py — Harness component #2: the tool registry & dispatch.

> Tools are the agent's hands. This module turns ordinary Python functions into
> model-callable tools (JSON-schema generation), validates the arguments the model
> sends, and dispatches to the implementation.

In context-primitive terms, tools are how SELECT happens: instead of dumping every
document into the window, you give the model a `search` / `read` tool and let it
pull the right tokens in at the point of use.

This module is WORKING (registry + schema generation + dispatch) with clearly
marked TODOs for the validation depth a production harness needs.

SECURITY: a tool is an action the *model* can trigger. Treat every tool input as
untrusted. Validate before executing, and route side-effecting tools through the
pre_tool approval hook (hooks.py). Never `exec()` model output in-process
(sandbox.py).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, get_args, get_origin

# Minimal Python-annotation → JSON-schema-type mapping. Extend as needed.
_PY_TO_JSON: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    func: Callable[..., Awaitable[str]]


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    """Turn a single parameter annotation into a JSON-schema fragment.

    Handles the common scalar types plus `list[T]`. TODO(student): extend to
    Optional[T], Literal[...] (→ enum), nested dataclasses, and `dict[str, T]`.
    """
    origin = get_origin(annotation)
    if origin in (list, list):
        (item_type,) = get_args(annotation) or (str,)
        return {
            "type": "array",
            "items": {"type": _PY_TO_JSON.get(item_type, "string")},
        }
    return {"type": _PY_TO_JSON.get(annotation, "string")}


class ToolRegistry:
    """A scoped collection of tools. Build one per agent/sub-agent.

    Having a *registry object* (rather than a global) matters for ISOLATE: a
    sub-agent (subagents.py) gets its own registry exposing only the tools it
    needs, keeping its context — and its blast radius — small.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def tool(self, func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
        """Decorator: register an async function as a tool on THIS registry."""
        sig = inspect.signature(func)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for pname, param in sig.parameters.items():
            properties[pname] = _annotation_to_schema(param.annotation)
            properties[pname]["description"] = f"{pname} argument"
            if param.default is inspect.Parameter.empty:
                required.append(pname)

        description = (func.__doc__ or func.__name__).strip().split("\n", 1)[0]
        self._tools[func.__name__] = ToolSpec(
            name=func.__name__,
            description=description,
            input_schema={
                "type": "object",
                "properties": properties,
                "required": required,
            },
            func=func,
        )
        return func

    def schemas(self) -> list[dict[str, Any]]:
        """The `tools=[...]` payload to hand the model."""
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
        ]

    def validate(self, name: str, args: dict[str, Any]) -> str | None:
        """Lightweight arg validation. Returns an error string, or None if OK.

        Checks: tool exists, all `required` keys present, no unexpected keys.
        TODO(student): add type checks against the schema (string vs int vs bool),
        enum membership, and array item types. The model WILL send malformed args;
        a clear error message lets it self-correct instead of looping.
        """
        spec = self._tools.get(name)
        if spec is None:
            return f"unknown tool {name!r}"
        schema = spec.input_schema
        required = set(schema.get("required", []))
        allowed = set(schema.get("properties", {}))
        missing = required - set(args)
        if missing:
            return f"missing required args: {sorted(missing)}"
        unexpected = set(args) - allowed
        if unexpected:
            return f"unexpected args: {sorted(unexpected)}"
        return None

    async def dispatch(self, name: str, args: dict[str, Any]) -> tuple[str, bool]:
        """Validate then run a tool. Returns (result_text, is_error).

        Never raises into the loop — a tool failure becomes a structured error the
        model sees as a tool_result, so it can adapt. That resilience is the
        harness's job, not the model's.
        """
        err = self.validate(name, args)
        if err is not None:
            return f"error: {err}", True
        spec = self._tools[name]
        try:
            return await spec.func(**args), False
        except Exception as exc:  # tool blew up → tell the model, keep the loop alive
            return f"error: {type(exc).__name__}: {exc}", True


# A convenience default registry + module-level decorator, mirroring the raw loop.
# Most harnesses prefer explicit per-agent registries (see above) — use this only
# for quick demos.
default_registry = ToolRegistry()
tool = default_registry.tool
