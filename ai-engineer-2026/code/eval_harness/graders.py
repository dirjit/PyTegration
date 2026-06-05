"""graders.py — Eval types #1 (deterministic) and #2 (LLM-as-judge).

> A grader maps (expected, actual) → pass/fail (+ optional score & reason). Pick
> the *cheapest grader that captures what you care about*: deterministic when the
> answer is exact/numeric, an LLM judge only when correctness is genuinely fuzzy.

Deterministic graders (exact / regex / numeric-tolerance) are WORKING and pure —
no API key, fully reproducible. The `llm_as_judge` grader ships with a
deterministic MOCK judge so the whole suite runs offline; the seam for a real
judge model is marked.

GOTCHA: prefer deterministic graders. An LLM judge is itself a model — it's
non-deterministic, costs tokens, and needs calibration against human labels.
Reach for it only when exact/regex/numeric can't express the criterion.
COST: every llm_as_judge call is a model call. On a 500-item dataset that's 500
extra calls per CI run — budget for it or gate it behind a deterministic pre-filter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class GradeResult:
    """The uniform output of every grader."""

    passed: bool
    score: float = 0.0          # 0.0–1.0; deterministic graders use 0/1
    reason: str = ""            # human-readable why (shows up in CI logs)


# ── Eval type #1: deterministic graders ──────────────────────────────────────


def grade_exact(expected: str, actual: str, *, strip: bool = True, ci: bool = True) -> GradeResult:
    """Exact-match grader. The cheapest, most reproducible check there is.

    `strip` trims surrounding whitespace; `ci` makes it case-insensitive. Use for
    classification labels, IDs, canonical short answers.
    """
    e, a = expected, actual
    if strip:
        e, a = e.strip(), a.strip()
    if ci:
        e, a = e.lower(), a.lower()
    ok = e == a
    return GradeResult(passed=ok, score=1.0 if ok else 0.0,
                       reason="exact match" if ok else f"expected {expected!r}, got {actual!r}")


def grade_regex(pattern: str, actual: str, *, flags: int = 0) -> GradeResult:
    """Regex-search grader: pass iff `pattern` is found in `actual`.

    Use when the right answer is "mentions X" or "contains a valid Y" rather than
    an exact string — e.g. "the answer includes a 4-digit year".
    """
    ok = re.search(pattern, actual, flags) is not None
    return GradeResult(passed=ok, score=1.0 if ok else 0.0,
                       reason=f"/{pattern}/ {'found' if ok else 'not found'}")


def grade_numeric(expected: float, actual: str | float, *, tol: float = 1e-6) -> GradeResult:
    """Numeric grader with absolute tolerance.

    Pulls the first number out of `actual` if it's a string. Use for "the total is
    $42.50" style answers where formatting varies but the value must be right.
    """
    try:
        value = actual if isinstance(actual, (int, float)) else _first_number(str(actual))
    except ValueError as exc:
        return GradeResult(passed=False, score=0.0, reason=str(exc))
    ok = abs(float(value) - float(expected)) <= tol
    return GradeResult(passed=ok, score=1.0 if ok else 0.0,
                       reason=f"|{value} - {expected}| {'<=' if ok else '>'} {tol}")


def _first_number(text: str) -> float:
    """Extract the first (optionally signed/decimal) number from text."""
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        raise ValueError(f"no number found in {text!r}")
    return float(m.group())


# ── Eval type #2: LLM-as-judge (with a 5-criterion rubric) ───────────────────


@dataclass
class Rubric:
    """A 5-criterion rubric for the LLM judge. Each criterion is scored 0–1; the
    item passes if the weighted average clears `pass_threshold`.

    The five criteria below are a sensible default for an answer-quality judge.
    Tune the weights per use case. GOTCHA: keep criteria *independently
    gradeable* and concrete ("cites a source") — vague criteria ("is good")
    produce noisy, uncalibrated judging.
    """

    relevance: float = 1.0      # weight: does it answer the actual question?
    correctness: float = 1.0    # weight: are the facts right?
    completeness: float = 1.0   # weight: does it cover the needed points?
    grounding: float = 1.0      # weight: is it supported / cited, not invented?
    safety: float = 1.0         # weight: no harmful / policy-violating content?
    pass_threshold: float = 0.7

    def criteria(self) -> dict[str, float]:
        return {
            "relevance": self.relevance,
            "correctness": self.correctness,
            "completeness": self.completeness,
            "grounding": self.grounding,
            "safety": self.safety,
        }


# A judge is a callable (question, expected, actual, rubric) -> per-criterion
# scores. The default is a deterministic MOCK so the suite runs offline.
Judge = Callable[[str, str, str, Rubric], dict[str, float]]


def _mock_judge(question: str, expected: str, actual: str, rubric: Rubric) -> dict[str, float]:
    """A deterministic stand-in for a real judge model — NO API key, NO network.

    It approximates "quality" with cheap heuristics (keyword overlap with the
    expected answer, length sanity, an absence-of-banned-words safety check) so
    the harness is runnable and tests are reproducible. It is NOT a real quality
    signal — it exists so the *plumbing* is exercised offline.

    # TODO(student): replace with a real judge model call. The production shape:
    #   resp = client.messages.create(
    #       model="claude-opus-4-8", max_tokens=1024,
    #       output_config={"format": {... per-criterion 0-1 scores ...}},
    #       system=JUDGE_SYSTEM, messages=[{"role":"user","content": prompt}])
    #   then CALIBRATE the judge against a few dozen human labels before trusting it.
    """
    exp_words = {w for w in re.findall(r"\w+", expected.lower()) if len(w) > 3}
    act_words = {w for w in re.findall(r"\w+", actual.lower()) if len(w) > 3}
    overlap = len(exp_words & act_words) / max(1, len(exp_words))

    banned = {"kill", "bomb", "exploit"}  # toy safety check
    safe = 0.0 if (act_words & banned) else 1.0
    has_content = 1.0 if actual.strip() else 0.0

    return {
        "relevance": overlap,
        "correctness": overlap,
        "completeness": min(1.0, overlap + 0.2) * has_content,
        "grounding": overlap,
        "safety": safe,
    }


def llm_as_judge(
    question: str,
    expected: str,
    actual: str,
    rubric: Rubric | None = None,
    *,
    judge: Judge | None = None,
) -> GradeResult:
    """Grade `actual` against `expected` using a rubric-driven judge.

    Computes a weighted average of the per-criterion scores and passes iff it
    clears `rubric.pass_threshold`. Defaults to the offline mock judge; pass a
    real `judge` callable for production.
    """
    rubric = rubric or Rubric()
    judge = judge or _mock_judge
    scores = judge(question, expected, actual, rubric)
    weights = rubric.criteria()

    total_w = sum(weights.values()) or 1.0
    weighted = sum(scores.get(k, 0.0) * w for k, w in weights.items()) / total_w
    ok = weighted >= rubric.pass_threshold

    detail = ", ".join(f"{k}={scores.get(k, 0.0):.2f}" for k in weights)
    return GradeResult(
        passed=ok,
        score=weighted,
        reason=f"judge score {weighted:.2f} (thr {rubric.pass_threshold}) [{detail}]",
    )
