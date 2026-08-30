"""trajectory.py — Eval type #3: trajectory / tool-sequence checks.

> A correct *answer* isn't always a correct *process*. Trajectory evals check that
> the agent took the right path: called the right tools, in the right order, with
> the right arguments. This catches agents that get lucky, or that skip a required
> step (e.g. "searched before answering"), even when the final text looks fine.

Pure, deterministic, offline. You feed it the agent's recorded trace (a list of
tool calls) and the expected sequence; it reports matches and the first divergence.

The "trace" shape this expects — a list of `{"name": ..., "input": {...}}` — is
exactly what `raw_agent_loop.py` / `mini_harness` produce, so you can record a run
and grade its trajectory directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TrajectoryResult:
    passed: bool
    reason: str = ""
    matched: int = 0  # how many expected steps matched in order
    expected_len: int = 0


def extract_tool_calls(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pull the ordered tool calls out of a recorded run trace.

    Accepts either:
      - a flat list of {"name", "input"} tool-call records, or
      - a message list (assistant turns containing tool_use content blocks),
    so it works on both a hand-built trace and a raw conversation transcript.
    """
    calls: list[dict[str, Any]] = []
    for entry in trace:
        # Flat tool-call record.
        if "name" in entry and "input" in entry and "content" not in entry:
            calls.append({"name": entry["name"], "input": entry.get("input", {})})
            continue
        # Conversation message: scan its content for tool_use blocks.
        content = entry.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls.append({"name": block["name"], "input": block.get("input", {})})
    return calls


def check_trajectory(
    trace: list[dict[str, Any]],
    expected_tools: list[str],
    *,
    expected_args: list[dict[str, Any]] | None = None,
    allow_extra: bool = True,
) -> TrajectoryResult:
    """Check the agent called `expected_tools` in order.

    Args:
      trace:          recorded run (tool-call records or message transcript).
      expected_tools: the ordered tool names the agent should have called.
      expected_args:  optional per-step required arg subsets — each dict must be a
                      subset of the actual call's input (checks the *right* args,
                      not just the right tool).
      allow_extra:    if True, the agent may call additional tools between the
                      expected ones (subsequence match). If False, the expected
                      sequence must be a contiguous prefix-style exact match.

    Returns a TrajectoryResult naming the first divergence — the actionable signal
    you want in CI ("expected web_search before write_file, but it wrote first").
    """
    actual = extract_tool_calls(trace)
    expected_len = len(expected_tools)

    if not allow_extra:
        # Strict: positions must line up one-to-one.
        for i, want in enumerate(expected_tools):
            if i >= len(actual):
                return TrajectoryResult(
                    False,
                    f"missing call #{i + 1}: expected {want!r}",
                    matched=i,
                    expected_len=expected_len,
                )
            if actual[i]["name"] != want:
                return TrajectoryResult(
                    False,
                    f"call #{i + 1}: expected {want!r}, got {actual[i]['name']!r}",
                    matched=i,
                    expected_len=expected_len,
                )
            if expected_args and not _args_subset(expected_args[i], actual[i]["input"]):
                return TrajectoryResult(
                    False,
                    f"call #{i + 1} ({want!r}): args mismatch",
                    matched=i,
                    expected_len=expected_len,
                )
        return TrajectoryResult(
            True, "trajectory matches (strict)", matched=expected_len, expected_len=expected_len
        )

    # Subsequence match: expected tools must appear in order, extras allowed.
    ai = 0
    for i, want in enumerate(expected_tools):
        while ai < len(actual) and actual[ai]["name"] != want:
            ai += 1
        if ai >= len(actual):
            return TrajectoryResult(
                False,
                f"did not find expected call {want!r} (step {i + 1}) in order",
                matched=i,
                expected_len=expected_len,
            )
        if (
            expected_args
            and i < len(expected_args)
            and not _args_subset(expected_args[i], actual[ai]["input"])
        ):
            return TrajectoryResult(
                False,
                f"call {want!r} (step {i + 1}): args mismatch",
                matched=i,
                expected_len=expected_len,
            )
        ai += 1
    return TrajectoryResult(
        True, "trajectory matches (subsequence)", matched=expected_len, expected_len=expected_len
    )


def _args_subset(required: dict[str, Any], actual: dict[str, Any]) -> bool:
    """True iff every key/value in `required` is present (and equal) in `actual`."""
    return all(actual.get(k) == v for k, v in required.items())
