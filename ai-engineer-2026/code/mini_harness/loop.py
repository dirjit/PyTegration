"""loop.py — Harness component #1 (+#9): the loop control & iteration guardrail.

> The while-loop that drives model -> tools -> model is the spine the other nine
> components hang off. This file wires them together: it calls the model, fires
> the hooks (#6), dispatches tools (#2), traces every step (#7), checkpoints
> after each iteration (#4), runs compaction (#3), and — critically — enforces a
> HARD iteration cap (#9).

This is the integration point. It's deliberately readable rather than clever: the
loop you'd recognize from `raw_agent_loop.py`, now with the harness seams wired
in. A few inner steps are left as `# TODO(student):` because they depend on the
parts you're meant to build (real compaction, real sub-agents).

HARD CAP (the guardrail): `HarnessConfig.max_iterations` bounds the loop. An
unbounded agent loop is an unbounded bill and a potential infinite loop in
production. Hitting the cap is a FAILURE to investigate, never normal completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .context import ContextManager
from .hooks import HookContext, HookRegistry, HookType
from .observability import span
from .persistence import Checkpointer
from .tools import ToolRegistry


# Reuse the same provider seam as the raw loop (provider-agnostic by design).
@dataclass
class ModelResponse:
    content: list[dict[str, Any]]
    stop_reason: str  # "tool_use" -> run tools and loop; otherwise -> done


class Provider(Protocol):
    async def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse: ...


@dataclass
class HarnessConfig:
    """All the knobs the loop needs, in one place."""

    run_id: str
    task: str
    provider: Provider
    tools: ToolRegistry
    context: ContextManager
    hooks: HookRegistry = field(default_factory=HookRegistry)
    checkpointer: Checkpointer | None = None
    max_iterations: int = 12  # THE guardrail (#9)


@dataclass
class LoopResult:
    final_text: str
    iterations: int
    status: str  # "done" | "stopped" | "error"
    messages: list[dict[str, Any]] = field(default_factory=list)


async def run_loop(config: HarnessConfig) -> LoopResult:
    """Drive the harness loop to completion or to the iteration cap.

    Resume support: if a checkpointer is provided and a run with this id exists,
    we pick up from its saved messages (durable execution). Otherwise we start
    fresh from the task.
    """
    cfg = config
    tool_schemas = cfg.tools.schemas()

    # ── Resume-or-start (component #4) ───────────────────────────────────────
    messages: list[dict[str, Any]]
    start_iteration = 1
    resumed = False
    if cfg.checkpointer is not None:
        existing = cfg.checkpointer.load_run(cfg.run_id)
        if existing is not None and existing.status == "running":
            messages = existing.messages
            start_iteration = existing.iteration + 1
            resumed = True
        else:
            messages = [{"role": "user", "content": cfg.task}]
            cfg.checkpointer.start_run(cfg.run_id, messages)
    else:
        messages = [{"role": "user", "content": cfg.task}]

    # Shared scratch dict so hooks can accumulate state (e.g. tool-call counts
    # for a budget stop) across the whole run.
    scratch: dict[str, Any] = {"tool_calls": 0}

    with span("run", run_id=cfg.run_id, resumed=resumed) as run_span:
        for iteration in range(start_iteration, cfg.max_iterations + 1):
            # ── COMPRESS (#3): compact history if we're near the window limit ──
            messages = cfg.context.maybe_compact(messages)

            # ── 1) Call the model (#1, traced #7) ──────────────────────────────
            with span("model_call", iteration=iteration) as s:
                response = await cfg.provider.generate(
                    system=cfg.context.assemble_system(),
                    messages=messages,
                    tools=tool_schemas,
                )
                s["stop_reason"] = response.stop_reason
                # TODO(student): set s["tokens"]/s["usd"] from real usage metadata
                # so spans double as your cost dashboard (see observability.py).

            # ── 2) Done? Run stop hooks, then return ──────────────────────────
            stop_ctx = HookContext(
                hook_type=HookType.STOP,
                run_id=cfg.run_id,
                iteration=iteration,
                scratch=scratch,
            )
            wants_stop = cfg.hooks.run_stop(stop_ctx)

            if response.stop_reason != "tool_use" or wants_stop:
                final = next((b["text"] for b in response.content if b["type"] == "text"), "")
                status = "stopped" if wants_stop else "done"
                if cfg.checkpointer is not None:
                    messages.append({"role": "assistant", "content": response.content})
                    cfg.checkpointer.save_step(cfg.run_id, iteration, messages, status=status)
                run_span["status"] = status
                return LoopResult(
                    final_text=final,
                    iterations=iteration,
                    status=status,
                    messages=messages,
                )

            # ── 3) Append assistant turn verbatim (ids needed for tool_results)─
            messages.append({"role": "assistant", "content": response.content})

            # ── 4) Execute each requested tool, through the hooks (#6, #2) ─────
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block["type"] != "tool_use":
                    continue
                name, args, call_id = block["name"], block["input"], block["id"]
                scratch["tool_calls"] += 1

                # PRE-TOOL hook: an approval gate / deny-list can BLOCK the call.
                pre_ctx = HookContext(
                    hook_type=HookType.PRE_TOOL,
                    run_id=cfg.run_id,
                    iteration=iteration,
                    tool_name=name,
                    tool_input=args,
                    scratch=scratch,
                )
                decision = cfg.hooks.run_pre_tool(pre_ctx)
                if decision is not None and decision.blocked:
                    result_text = decision.replacement_result or f"blocked: {decision.reason}"
                    is_error = True
                else:
                    with span("tool", tool_name=name, iteration=iteration) as ts:
                        result_text, is_error = await cfg.tools.dispatch(name, args)
                        ts["is_error"] = is_error

                # POST-TOOL hook: audit / redact / meter. May mutate result.
                post_ctx = HookContext(
                    hook_type=HookType.POST_TOOL,
                    run_id=cfg.run_id,
                    iteration=iteration,
                    tool_name=name,
                    tool_input=args,
                    result=result_text,
                    is_error=is_error,
                    scratch=scratch,
                )
                cfg.hooks.run_post_tool(post_ctx)
                result_text = post_ctx.result or result_text

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "content": result_text,
                        "is_error": is_error,
                    }
                )

            # ── 5) Feed results back, then CHECKPOINT (#4) and loop ────────────
            messages.append({"role": "user", "content": tool_results})
            if cfg.checkpointer is not None:
                cfg.checkpointer.save_step(cfg.run_id, iteration, messages, status="running")

        # ── Fell out of the loop -> hit the hard cap (#9). This is a failure. ──
        if cfg.checkpointer is not None:
            cfg.checkpointer.save_step(cfg.run_id, cfg.max_iterations, messages, status="stopped")
        run_span["status"] = "stopped"
        return LoopResult(
            final_text="(stopped: hit max_iterations guardrail before finishing)",
            iterations=cfg.max_iterations,
            status="stopped",
            messages=messages,
        )
