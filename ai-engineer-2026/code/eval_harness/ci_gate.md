# The CI gate — block regressions on merge

> **Goal:** make "did this change make the agent worse?" a red/green check that
> blocks the merge — the Phase 4 deliverable.

`runner.py` already exits **nonzero** when the pass rate falls below an absolute
threshold. That alone is a usable gate. But absolute thresholds are blunt: a suite
that legitimately sits at 84% shouldn't pass at `--threshold 0.8` forever while
silently drifting down to 80%. The better gate compares each run against a
**stored baseline** and fails when the pass rate **drops 3+ points**.

## The two gate modes

| Mode | Fails when | Use it for |
|------|------------|------------|
| **Absolute** (built into `runner.py`) | `pass_rate < --threshold` | A hard floor you never want to cross. |
| **Baseline delta** (below) | `pass_rate < baseline − 3pts` | Day-to-day regression detection in PRs. |

**WHY a delta, not just a floor:** evals are noisy and improve over time. A delta
gate catches "this PR made things worse" even when you're still above the floor,
and it ratchets the baseline up as you improve — so you can't regress back down to
a number that used to be acceptable.

## Wiring the baseline delta

Store a `baseline.txt` (a single number, the committed pass rate) next to the
dataset, and update it deliberately when a change is a real improvement. A thin
wrapper around `run_eval` does the comparison:

```python
# scripts/ci_eval.py  (sketch — build this in Phase 4)
import sys
from pathlib import Path
from eval_harness.dataset import load_golden
from eval_harness.runner import run_eval, mock_agent, print_report

REGRESSION_PTS = 3.0  # fail on a 3-point-or-worse drop

baseline = float(Path("eval_harness/baseline.txt").read_text().strip())
items = load_golden("eval_harness/golden.jsonl")
report = run_eval(mock_agent, items)          # swap mock_agent for your real agent
print_report(report, baseline / 100)

current = report.pass_rate * 100
drop = baseline - current
if drop >= REGRESSION_PTS:
    print(f"❌ REGRESSION: {current:.1f}% is {drop:.1f}pts below baseline {baseline:.1f}%")
    sys.exit(1)
print(f"✅ {current:.1f}% vs baseline {baseline:.1f}% (drop {max(0, drop):.1f}pts < {REGRESSION_PTS})")
```

**COST:** every CI run with `judge` items is a batch of model calls. Pin a small,
fast judge model and consider gating judge items behind a deterministic pre-filter
so PR cycles stay cheap. Run the full suite on `main`; run a cheaper subset on PRs.

## Example GitHub Actions workflow

`.github/workflows/eval-gate.yml`:

```yaml
name: agent-eval-gate

on:
  pull_request:
  push:
    branches: [main]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      # The offline path needs NO secrets — the mock judge runs without an API
      # key. For a real judge model, add ANTHROPIC_API_KEY as a repo secret and
      # reference it here (auth brokering: the key lives in CI secrets, never in
      # the dataset or the code).
      # env:
      #   ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Run eval gate (absolute floor)
        run: |
          python code/eval_harness/runner.py \
            --dataset code/eval_harness/golden.jsonl \
            --threshold 0.80
        # runner.py exits 1 below threshold → this step fails → the check is red.

      # Optional: the baseline-delta gate (richer signal for PRs)
      # - name: Run eval gate (baseline delta)
      #   run: python code/scripts/ci_eval.py
```

Mark the `eval` check as **required** in your branch-protection rules. Now a PR
that drops the pass rate cannot be merged — the gate is the thing standing between
a quiet regression and production.

## What "you've got it" looks like (exit check)

- A bad change to your agent turns the CI check **red** before it can merge.
- The report breaks the pass rate down **by difficulty level**, so a hard-case
  regression isn't hidden by easy wins.
- Improving the agent and bumping `baseline.txt` is a deliberate, reviewed step.

➡️ Next: expand the golden set, calibrate the judge against human labels, and add
contamination defenses (Phase 4 lessons).
