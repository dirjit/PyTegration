"""mini_harness — a Phase 3 SKELETON for building the harness layer yourself.

> **Goal (Phase 3):** build, by hand, the ~1,500-line "OS" that turns a raw model
> API into a system that can act, remember, recover, and be measured.

This package is the *scaffold*. The hard parts are yours to write — they're marked
`# TODO(student):`. The simple-but-load-bearing parts (hooks, persistence,
observability, the tool registry) are implemented so you have a spine to build on.

## The 10 components of a modern harness (and where each lives here)

| # | Component                | Module               | Status in skeleton        |
|---|--------------------------|----------------------|---------------------------|
| 1 | Loop control             | `loop.py`            | spine + TODOs             |
| 2 | Tool dispatch            | `tools.py`           | WORKING registry + TODOs  |
| 3 | Context assembly         | `context.py`         | assembly done; compaction TODO |
| 4 | Memory / persistence     | `persistence.py`     | WORKING (stdlib sqlite3)  |
| 5 | Sub-agent orchestration  | `subagents.py`       | skeleton + TODOs          |
| 6 | Hooks (pre/post/stop)    | `hooks.py`           | WORKING                   |
| 7 | Observability / tracing  | `observability.py`   | WORKING (OTEL-optional)   |
| 8 | Sandboxing & auth broker | `sandbox.py`         | placeholder + SECURITY    |
| 9 | Guardrails (iteration cap)| `loop.py`           | WORKING                   |
|10 | Evals & CI gates         | ../eval_harness/     | Phase 4 scaffold          |

These map onto the 4 context primitives (Lesson 04): `context.py` is WRITE +
COMPRESS, `tools.py` is SELECT (retrieve at point of use), `subagents.py` is
ISOLATE.

Everything here runs offline with stdlib only — no third-party import is required
to load this package.
"""

from __future__ import annotations

from .hooks import HookRegistry, HookType
from .loop import HarnessConfig, LoopResult, run_loop
from .observability import span
from .persistence import Checkpointer
from .tools import ToolRegistry, tool

__all__ = [
    "Checkpointer",
    "HarnessConfig",
    "HookRegistry",
    "HookType",
    "LoopResult",
    "ToolRegistry",
    "run_loop",
    "span",
    "tool",
]
