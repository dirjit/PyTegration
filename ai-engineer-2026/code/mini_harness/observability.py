"""observability.py — Harness component #7: lightweight span/tracing.

> You cannot fix what you cannot see. Every interesting step of the loop (a model
> call, a tool execution, a compaction) should be wrapped in a *span* so you can
> reconstruct what happened, how long it took, and where the tokens/dollars went.

This module is WORKING. It exposes a single `span(...)` context manager that:
  - uses **OpenTelemetry** if it's installed (so you get real distributed traces
    in LangSmith / Braintrust / Phoenix for free), and
  - falls back to **stdlib logging** otherwise — so the harness runs offline with
    zero third-party dependencies.

OTEL is *optional*: importing this module never requires it. That's the
"provider-agnostic, offline by default" rule the whole `code/` tree follows.

COST: attach `tokens` / `usd` attributes to spans and your tracing backend
becomes your cost dashboard for free — no separate metering pipeline.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger("mini_harness")
if not logger.handlers:
    # Configure a default handler so spans are visible when run as a script.
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


# Detect OpenTelemetry once, at import. If absent, `_tracer` stays None and we use
# the stdlib fallback. Either way, callers use the same `span(...)` API.
try:  # pragma: no cover - exercised only when OTEL is installed
    from opentelemetry import trace as _otel_trace  # type: ignore

    _tracer: Any = _otel_trace.get_tracer("mini_harness")
except Exception:  # ImportError, or a broken partial install
    _tracer = None


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
    """Open a tracing span named `name` with the given attributes.

    Yields a mutable dict you can add attributes to mid-span (e.g. token counts
    discovered only after the model returns):

        with span("model_call", iteration=3) as s:
            resp = provider.generate(...)
            s["tokens"] = resp.usage.total

    With OTEL installed this becomes a real span; without it, it logs start/stop
    and duration via stdlib logging. Exceptions are recorded and re-raised.
    """
    attrs: dict[str, Any] = dict(attributes)

    if _tracer is not None:  # pragma: no cover
        with _tracer.start_as_current_span(name) as otel_span:
            for k, v in attrs.items():
                otel_span.set_attribute(k, v)
            try:
                yield attrs
            finally:
                # Flush any attributes added during the span.
                for k, v in attrs.items():
                    otel_span.set_attribute(k, v)
        return

    # ── stdlib fallback ──────────────────────────────────────────────────────
    start = time.perf_counter()
    logger.info("span.start name=%s attrs=%s", name, attrs)
    try:
        yield attrs
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error("span.error name=%s ms=%.1f err=%s", name, elapsed_ms, exc)
        raise
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("span.end   name=%s ms=%.1f attrs=%s", name, elapsed_ms, attrs)


# TODO(student): add a `record_usage(tokens, usd)` helper that accumulates a
# per-run total and emits it as a final span attribute — your run-level cost line.
