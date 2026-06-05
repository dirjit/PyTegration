"""eval_harness — Phase 4 scaffold: the eval & regression harness.

> **Goal (Phase 4):** prove with evals that the next change made the agent
> *better*, not worse — and wire a CI gate that blocks merges when it regresses.

The brutal-truth from the curriculum README: teams can call an LLM; far fewer can
*measure and harden* one. That gap is the job. This package is the measuring rig.

## The 4 eval types (and where each lives)

| Eval type            | What it answers                              | Module          |
|----------------------|----------------------------------------------|-----------------|
| 1. Deterministic     | Did the output exactly/numerically match?    | `graders.py`    |
| 2. LLM-as-judge      | Is the output *good* on fuzzy criteria?      | `graders.py`    |
| 3. Trajectory        | Did it call the right tools in the right order? | `trajectory.py` |
| 4. Golden-dataset    | Pass rate across a curated, leveled dataset  | `dataset.py` + `runner.py` |

`runner.py` ties them together and returns a NONZERO EXIT CODE when the pass rate
drops below a threshold — that exit code is the CI gate (`ci_gate.md`).

Everything runs offline: the LLM judge has a deterministic MOCK so there's no API
key and no network. Swap in a real judge model for production calibration.
"""

from __future__ import annotations

from .dataset import GoldenItem, load_golden
from .graders import (
    Rubric,
    grade_exact,
    grade_numeric,
    grade_regex,
    llm_as_judge,
)
from .trajectory import check_trajectory

__all__ = [
    "GoldenItem",
    "Rubric",
    "check_trajectory",
    "grade_exact",
    "grade_numeric",
    "grade_regex",
    "llm_as_judge",
    "load_golden",
]
