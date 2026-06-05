"""dataset.py — Eval type #4 foundation: the golden dataset loader.

> A "golden" dataset is a curated set of inputs with known-good expected outputs,
> spread across difficulty levels. It's the ruler you measure every change with.

This loads JSONL (one JSON object per line) into typed `GoldenItem`s. JSONL is the
right format for eval data: append-only, diff-friendly in code review, and
streamable for large sets.

GOTCHA — contamination: keep the golden set OUT of anything the model trains on or
sees at dev time, and version it. A dataset the agent has effectively memorized
measures nothing. (Phase 4 expands on contamination defenses.)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GoldenItem:
    """One eval case.

    Fields:
      id:         stable identifier (shows up in CI output).
      level:      difficulty — "easy" | "medium" | "hard". Report pass rate per
                  level so a regression on hard cases isn't masked by easy ones.
      question:   the input handed to the agent-under-test.
      expected:   the known-good answer (for deterministic / judge grading).
      grader:     which grader to use — "exact" | "regex" | "numeric" | "judge".
      grader_arg: optional grader parameter (e.g. the regex pattern, or numeric tol).
      expected_tools: optional ordered tool names for trajectory checks (type #3).
    """

    id: str
    level: str
    question: str
    expected: str
    grader: str = "exact"
    grader_arg: Any = None
    expected_tools: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GoldenItem:
        return cls(
            id=d["id"],
            level=d.get("level", "medium"),
            question=d["question"],
            expected=d["expected"],
            grader=d.get("grader", "exact"),
            grader_arg=d.get("grader_arg"),
            expected_tools=list(d.get("expected_tools", [])),
        )


def load_golden(path: str | Path) -> list[GoldenItem]:
    """Load a golden dataset from a JSONL file. Skips blank lines and `#` comments.

    Raises a clear error (with the line number) on malformed JSON so a typo in the
    dataset fails loudly in CI rather than silently dropping a case.
    """
    items: list[GoldenItem] = []
    p = Path(path)
    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{p}:{lineno}: invalid JSON: {exc}") from exc
        items.append(GoldenItem.from_dict(obj))
    return items
