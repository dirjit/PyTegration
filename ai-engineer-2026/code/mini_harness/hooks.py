"""hooks.py — Harness component #6: a pluggable pre_tool / post_tool / stop registry.

> The harness owns the *seams*. Hooks are where you bolt in policy without
> rewriting the loop: audit logging, an approval gate before a destructive tool,
> a cost ceiling, a PII redactor, a custom stop condition.

This module is WORKING code — it's simple enough to finish in the scaffold so the
rest of the harness has somewhere to hang behavior. The Claude Agent SDK exposes
the same idea (PreToolUse / PostToolUse / Stop hooks); you're rebuilding it.

Hook contract:
  - pre_tool(ctx)  → may return a `HookDecision` to BLOCK a tool call (e.g. a
                     human-in-the-loop gate, or a deny-list). Return None to allow.
  - post_tool(ctx) → observe/transform a tool result (audit, redact, meter cost).
  - stop(ctx)      → return True to stop the loop early (e.g. budget exhausted).

SECURITY: the pre_tool hook is the natural home for an approval gate on
irreversible actions (send_email, delete, external POST). Promote such actions to
dedicated tools (see tools.py) so a hook can intercept them by name.
COST: a post_tool or stop hook is where you enforce a token/$ budget — increment a
counter and stop the loop when it's blown, rather than discovering it on the bill.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class HookType(str, Enum):
    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    STOP = "stop"


@dataclass
class HookContext:
    """Everything a hook might need to make a decision.

    Populated by the loop before each hook fires. Not all fields are set for
    every hook type (e.g. `result` is None for a pre_tool hook).
    """

    hook_type: HookType
    run_id: str
    iteration: int
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    result: str | None = None          # set for post_tool
    is_error: bool = False             # set for post_tool
    scratch: dict[str, Any] = field(default_factory=dict)  # cross-hook shared state


@dataclass
class HookDecision:
    """Returned by a pre_tool hook to BLOCK a call. None = allow."""

    blocked: bool
    reason: str = ""
    # Optional replacement result surfaced to the model in place of the tool run
    # (e.g. "denied by approval gate"). Lets the model adapt instead of crashing.
    replacement_result: str | None = None


# A hook is just a callable taking the context. Return type varies by hook type:
#   pre_tool → HookDecision | None
#   post_tool → None (mutates ctx.result in place if it wants to transform)
#   stop → bool
Hook = Callable[[HookContext], Any]


class HookRegistry:
    """Holds the registered hooks and runs them in registration order."""

    def __init__(self) -> None:
        self._hooks: dict[HookType, list[Hook]] = {ht: [] for ht in HookType}

    def register(self, hook_type: HookType, hook: Hook) -> None:
        """Add a hook. Hooks run in the order they were registered."""
        self._hooks[hook_type].append(hook)

    def on(self, hook_type: HookType) -> Callable[[Hook], Hook]:
        """Decorator form: `@hooks.on(HookType.PRE_TOOL)`."""

        def deco(fn: Hook) -> Hook:
            self.register(hook_type, fn)
            return fn

        return deco

    # — invocation helpers the loop calls ————————————————————————————————

    def run_pre_tool(self, ctx: HookContext) -> HookDecision | None:
        """Run pre_tool hooks; first one to BLOCK wins (fail-closed)."""
        for hook in self._hooks[HookType.PRE_TOOL]:
            decision = hook(ctx)
            if isinstance(decision, HookDecision) and decision.blocked:
                return decision
        return None

    def run_post_tool(self, ctx: HookContext) -> HookContext:
        """Run post_tool hooks in order; each may mutate `ctx.result` in place."""
        for hook in self._hooks[HookType.POST_TOOL]:
            hook(ctx)
        return ctx

    def run_stop(self, ctx: HookContext) -> bool:
        """Run stop hooks; if ANY returns True, the loop should stop."""
        return any(bool(hook(ctx)) for hook in self._hooks[HookType.STOP])


# ── Example hooks (use these as templates; they're real and work) ────────────


def audit_log_hook(ctx: HookContext) -> None:
    """A post_tool hook that prints an audit line. Replace `print` with your
    structured logger / observability span in production."""
    status = "ERROR" if ctx.is_error else "ok"
    print(f"[audit] run={ctx.run_id} it={ctx.iteration} tool={ctx.tool_name} -> {status}")


def make_approval_gate(deny: set[str]) -> Hook:
    """Factory for a pre_tool hook that blocks tools whose name is in `deny`.

    SECURITY: this is the human-in-the-loop / deny-list pattern. In a real system
    you'd prompt an operator or check a policy engine here instead of a static set.
    """

    def gate(ctx: HookContext) -> HookDecision | None:
        if ctx.tool_name in deny:
            return HookDecision(
                blocked=True,
                reason=f"tool {ctx.tool_name!r} is on the deny-list",
                replacement_result=f"[blocked] {ctx.tool_name} requires approval",
            )
        return None

    return gate


def make_budget_stop(max_tool_calls: int) -> Hook:
    """Factory for a stop hook that halts the loop after N tool calls.

    COST: the cheapest possible budget guard. A production version would count
    tokens or dollars (from usage metadata) rather than raw calls.
    """

    def stop(ctx: HookContext) -> bool:
        count = ctx.scratch.get("tool_calls", 0)
        return count >= max_tool_calls

    return stop


# TODO(student): add a PII-redaction post_tool hook that scrubs emails/tokens
# from `ctx.result` before it re-enters the context window (a Write-primitive
# safety net — don't persist secrets the model surfaced).
