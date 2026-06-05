# `code/` — runnable scaffolds

> Type the code. Do not copy-paste the agent loop. Muscle memory is the point.

These are the runnable companions to the curriculum. Each one is a teaching
scaffold you **read and extend** — the simple, load-bearing parts are implemented
so you have a spine; the hard parts are marked `# TODO(student):` because building
them *is* the phase project.

## Provider-agnostic, offline by default — runs with NO API key

Every scaffold here runs with **only the Python standard library + `asyncio`**.
There are **no third-party import-time dependencies**. Each one talks to models
through a small `Provider` seam (a `Protocol`) and ships a deterministic, offline
**MOCK** provider/judge so you can run the whole thing without an API key, a
network, or a bill.

To go live: install the SDK (`pip install anthropic`), set `ANTHROPIC_API_KEY`,
and swap the mock for the real provider — the commented `AnthropicProvider` stub
in `raw_agent_loop.py` shows exactly where (it defaults to **Claude Opus 4.8** with
adaptive thinking). The loop code never changes; that's the payoff of coding to
the seam.

> **SECURITY / auth brokering:** the API key is always read from the environment
> by the SDK — never hardcoded, never passed into a tool, never exposed to the
> sandbox. Credentials live in the harness.

## The scaffolds

| Scaffold | Phase | Demonstrates | Run it |
|----------|-------|--------------|--------|
| [`raw_agent_loop.py`](raw_agent_loop.py) | **1 — First agent** | The agent loop from scratch: model → parse `tool_use` → execute tool → append `tool_result` → loop, with a **hard iteration cap**. Three example tools (mock `web_search`, real sandboxed `read_file`/`write_file`). Maps to the WRITE + SELECT primitives. | `python raw_agent_loop.py` |
| [`mini_harness/`](mini_harness/) | **3 — Build the harness** | A skeleton of the ~1,500-line mini-harness: the 10 harness components as modules. Working: tool registry, hooks, persistence (SQLite), observability, loop spine. `# TODO(student):` for compaction, sub-agents, sandboxing. | `python -c "import mini_harness"` (import smoke test); wire it up per the lesson |
| [`eval_harness/`](eval_harness/) | **4 — Evals & CI gate** | The 4 eval types: deterministic graders, an offline LLM-as-judge with a 5-criterion rubric, trajectory checks, and a golden-dataset runner that **exits nonzero on regression** (the CI gate). | `python eval_harness/runner.py` |

## `mini_harness/` — the 10 harness components

The harness is the "OS" you build around the model (Lesson 04). Each module is one
component; the table in [`mini_harness/__init__.py`](mini_harness/__init__.py) maps
them out. Quick tour:

- `loop.py` — **loop control + the iteration guardrail** (wires everything together)
- `tools.py` — **tool dispatch**: `@tool` → JSON-schema registry + arg validation
- `context.py` — **context assembly + compaction** (WRITE + COMPRESS primitives)
- `persistence.py` — **checkpointing** to SQLite, resume by `run_id` (WORKING)
- `subagents.py` — **sub-agent spawn** with an isolated window (ISOLATE primitive)
- `hooks.py` — **pre_tool / post_tool / stop** hook registry (WORKING)
- `observability.py` — **span/tracing**, OTEL-optional, stdlib fallback (WORKING)
- `sandbox.py` — **sandboxing & auth brokering** placeholder, with the SECURITY rules

## `eval_harness/` — the measuring rig

| File | What it is |
|------|------------|
| `graders.py` | Deterministic graders (exact / regex / numeric-tolerance) + `llm_as_judge` (offline mock) + the 5-criterion `Rubric`. |
| `dataset.py` | Golden-dataset loader (JSONL → typed `GoldenItem`). |
| `golden.jsonl` | ~5 example items across easy / medium / hard. |
| `trajectory.py` | Check the agent called the right tools in the right order. |
| `runner.py` | Run the dataset, apply graders, compute pass rate, **exit nonzero below threshold** — the CI gate. |
| `ci_gate.md` | The gate doc + a GitHub Actions workflow that blocks a 3+ point regression. |

```sh
python eval_harness/runner.py            # runs the offline mock agent
echo $?                                  # 0 = gate passed, 1 = regression
python eval_harness/runner.py --threshold 1.1   # demo a failing gate (exit 1)
```

## The throughline

`raw_agent_loop.py` shows the **loop**. `mini_harness/` makes that loop
**reliable, observable, durable, and safe**. `eval_harness/` **proves** a change
made it better, not worse. That arc — loop → harness → evals — is the whole
curriculum in three runnable pieces.

➡️ Start with [`raw_agent_loop.py`](raw_agent_loop.py), then read the Phase 3 and
Phase 4 lessons alongside the matching scaffold.
