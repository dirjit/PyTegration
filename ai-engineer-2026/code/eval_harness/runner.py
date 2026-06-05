"""runner.py — Eval type #4 + the CI gate.

> This is the part that pays the rent. It runs the golden dataset through a
> callable-under-test, applies the right grader to each item, computes the pass
> rate (overall and per difficulty level), and EXITS NONZERO when the pass rate
> falls below a threshold — turning "did this change make the agent worse?" into a
> red/green CI check that blocks the merge.

Run it directly to see the gate in action against a built-in MOCK agent (offline,
no API key):

    $ python eval_harness/runner.py
    $ echo $?          # 0 = gate passed, 1 = regression / below threshold

The mock agent is intentionally imperfect so you can watch the gate distinguish
pass from fail. Point `--agent` at your real agent (any `def agent(question) ->
str | (str, trace)`) to grade it.

See `ci_gate.md` for the GitHub Actions wiring that compares against a stored
baseline and blocks a 3+ point drop.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# Support running both as a module (`python -m eval_harness.runner`) and as a
# script (`python eval_harness/runner.py`).
if __package__ in (None, ""):  # script mode: make the package importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from eval_harness.dataset import GoldenItem, load_golden
    from eval_harness.graders import (
        Rubric,
        grade_exact,
        grade_numeric,
        grade_regex,
        llm_as_judge,
    )
    from eval_harness.trajectory import check_trajectory
else:
    from .dataset import GoldenItem, load_golden
    from .graders import Rubric, grade_exact, grade_numeric, grade_regex, llm_as_judge
    from .trajectory import check_trajectory


# An agent-under-test takes a question and returns either a plain answer string,
# or (answer, trace) where trace is a list of recorded tool calls for trajectory
# checks. This loose contract lets you grade anything from a one-liner to the
# full mini_harness loop.
AgentFn = Callable[[str], "str | tuple[str, list[dict[str, Any]]]"]


@dataclass
class ItemOutcome:
    id: str
    level: str
    passed: bool
    reason: str


@dataclass
class EvalReport:
    outcomes: list[ItemOutcome] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def passed(self) -> int:
        return sum(1 for o in self.outcomes if o.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def by_level(self) -> dict[str, tuple[int, int]]:
        """level -> (passed, total)."""
        agg: dict[str, list[int]] = {}
        for o in self.outcomes:
            slot = agg.setdefault(o.level, [0, 0])
            slot[1] += 1
            if o.passed:
                slot[0] += 1
        return {k: (v[0], v[1]) for k, v in agg.items()}


def _grade_item(item: GoldenItem, answer: str, trace: list[dict[str, Any]]) -> tuple[bool, str]:
    """Apply the item's declared grader, then (if specified) the trajectory check.

    BOTH must pass: an item that gets the right answer via the wrong process still
    fails its trajectory check. This is how "looks right but skipped the search"
    gets caught.
    """
    grader = item.grader
    if grader == "exact":
        res = grade_exact(item.expected, answer)
    elif grader == "regex":
        res = grade_regex(str(item.grader_arg or item.expected), answer)
    elif grader == "numeric":
        tol = float(item.grader_arg) if item.grader_arg is not None else 1e-6
        res = grade_numeric(_first_float(item.expected), answer, tol=tol)
    elif grader == "judge":
        res = llm_as_judge(item.question, item.expected, answer, Rubric())
    else:
        return False, f"unknown grader {grader!r}"

    if not res.passed:
        return False, res.reason

    # Trajectory check (eval type #3), if the item declares an expected sequence.
    if item.expected_tools:
        traj = check_trajectory(trace, item.expected_tools)
        if not traj.passed:
            return False, f"answer ok but trajectory failed: {traj.reason}"
        return True, f"{res.reason}; trajectory ok"

    return True, res.reason


def _first_float(text: str) -> float:
    import re

    m = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(m.group()) if m else 0.0


def run_eval(agent: AgentFn, items: list[GoldenItem]) -> EvalReport:
    """Run every golden item through `agent` and grade the result."""
    report = EvalReport()
    for item in items:
        out = agent(item.question)
        if isinstance(out, tuple):
            answer, trace = out
        else:
            answer, trace = out, []
        passed, reason = _grade_item(item, answer, trace)
        report.outcomes.append(ItemOutcome(item.id, item.level, passed, reason))
    return report


# ── The built-in MOCK agent (offline, deterministic) ─────────────────────────
# Intentionally imperfect — answers the easy/medium items correctly but is meant
# to let you SEE the gate working. Replace with your real agent via --agent.

def mock_agent(question: str) -> "str | tuple[str, list[dict[str, Any]]]":
    """A canned agent that returns plausible answers + a fake trace where needed."""
    q = question.lower()
    if "capital of france" in q:
        return "Paris"
    if "6 times 7" in q:
        return "42"
    if "moon landing" in q:
        return "The first crewed moon landing was in 1969 (Apollo 11)."
    if "define" in q and "harness" in q:
        return "A harness is the system around the model that adds the agent loop, tools, context, memory, and evals."
    if "research what a harness" in q:
        # Returns an answer AND a trace, so the trajectory check can run.
        answer = "A harness is everything between your code and the model API, saved to findings.md."
        trace = [
            {"name": "web_search", "input": {"query": "what is a harness"}},
            {"name": "write_file", "input": {"path": "findings.md", "content": "..."}},
        ]
        return answer, trace
    return "I don't know."


def _load_agent(spec: str) -> AgentFn:
    """Load an agent callable from a 'module:function' spec (e.g. 'myagent:run')."""
    mod_name, _, fn_name = spec.partition(":")
    module = importlib.import_module(mod_name)
    return getattr(module, fn_name)


def print_report(report: EvalReport, threshold: float) -> None:
    print("── EVAL REPORT ──")
    for o in report.outcomes:
        mark = "PASS" if o.passed else "FAIL"
        print(f"  [{mark}] {o.id:<16} ({o.level:<6}) {o.reason}")
    print()
    for level, (p, t) in sorted(report.by_level().items()):
        print(f"  {level:<6}: {p}/{t} ({p / t:.0%})")
    print(f"\n  OVERALL: {report.passed}/{report.total} = {report.pass_rate:.1%}"
          f"  (threshold {threshold:.1%})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the golden dataset and gate on pass rate.")
    parser.add_argument(
        "--dataset",
        default=str(Path(__file__).resolve().parent / "golden.jsonl"),
        help="path to the golden JSONL dataset",
    )
    parser.add_argument(
        "--agent",
        default=None,
        help="'module:function' of the agent under test (default: built-in mock_agent)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="minimum pass rate; below this the gate fails (exit 1)",
    )
    args = parser.parse_args(argv)

    items = load_golden(args.dataset)
    agent = _load_agent(args.agent) if args.agent else mock_agent

    report = run_eval(agent, items)
    print_report(report, args.threshold)

    # ── THE CI GATE ──────────────────────────────────────────────────────────
    # Below the absolute threshold → fail the build. ci_gate.md shows the richer
    # "regressed 3+ points vs a stored baseline" variant for day-to-day CI.
    if report.pass_rate < args.threshold:
        print(f"\n❌ GATE FAILED: pass rate {report.pass_rate:.1%} < threshold {args.threshold:.1%}")
        return 1
    print(f"\n✅ GATE PASSED: pass rate {report.pass_rate:.1%} >= threshold {args.threshold:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
