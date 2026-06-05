"""subagents.py — Harness component #5: sub-agent orchestration (the ISOLATE primitive).

> Give a focused sub-task its OWN clean context window. The sub-agent burns through
> dozens of noisy tool results in isolation and hands the parent back only a short
> summary — so the parent's window stays clean and dense.

This is the ISOLATE primitive (Lesson 04) made concrete. This module is a
SKELETON: the spawn boundary and the compressed-summary contract are sketched;
the student wires it to the real loop and a real summarizer.

COST: isolation is powerful but expensive — sub-agents multiply token usage (often
~15× for heavy multi-agent setups). The Lesson-04 caveat applies: spawn a
sub-agent only when the value clears that bar, not reflexively. Opus-class models
tend to under- *and* over-spawn depending on prompting; gate it explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class SubAgentResult:
    """What a sub-agent returns to its parent: a SHORT summary, not a raw dump.

    The whole point of ISOLATE is that `summary` is small. The parent never sees
    `raw_messages` (kept only for debugging/observability), so the noisy
    intermediate work stays out of the parent's window.
    """

    summary: str
    iterations: int
    raw_messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SubAgentSpec:
    """Defines an isolated sub-task: its own prompt, its own (smaller) tool set,
    its own iteration cap. A separate tool registry here is what makes the
    isolation real — the sub-agent literally cannot call tools you didn't grant."""

    name: str
    system_prompt: str
    task: str
    tool_schemas: list[dict[str, Any]] = field(default_factory=list)
    max_iterations: int = 6  # sub-agents should be tightly bounded


async def spawn(
    spec: SubAgentSpec,
    *,
    run_subloop: Callable[..., Awaitable[list[dict[str, Any]]]],
    summarize: Callable[[list[dict[str, Any]]], Awaitable[str]],
) -> SubAgentResult:
    """Run a sub-agent in an ISOLATED context and return a compressed summary.

    The two injected callables are the seams a student fills in:
      - `run_subloop(...)` drives the model→tools loop with a FRESH message list
        (a brand-new window — that's the isolation), returning the final messages.
      - `summarize(messages)` compresses that transcript into a short paragraph
        for the parent (COMPRESS applied at the isolation boundary).

    # TODO(student):
    #   1. Build a fresh `messages = [{"role": "user", "content": spec.task}]`.
    #      Do NOT pass the parent's history in — isolation means a clean window.
    #   2. Call `run_subloop` with spec.system_prompt, that fresh messages list,
    #      spec.tool_schemas, and spec.max_iterations (its own hard cap).
    #   3. Summarize the result with `summarize(...)` and return SubAgentResult.
    #   4. (Optional) run several specs concurrently with asyncio.gather for the
    #      parallel-research pattern — but mind the COST caveat above.
    #
    # The placeholder below documents the contract and returns a stub so the
    # skeleton imports and runs.
    """
    fresh_messages: list[dict[str, Any]] = [{"role": "user", "content": spec.task}]

    final_messages = await run_subloop(
        system=spec.system_prompt,
        messages=fresh_messages,
        tools=spec.tool_schemas,
        max_iterations=spec.max_iterations,
    )

    summary = await summarize(final_messages)
    return SubAgentResult(
        summary=summary,
        iterations=len(final_messages),
        raw_messages=final_messages,
    )
