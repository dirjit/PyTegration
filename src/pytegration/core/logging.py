"""Structured JSON logging with secret redaction.

LESSON: Module 9 (Observability). See docs/09-observability.md
LAYER:  core (infrastructure)

WHY structured (JSON) logs?
    In production, logs are ingested by tools (CloudWatch, Datadog, Loki, ELK).
    A line like `{"level":"INFO","msg":"task created","task_id":42}` is queryable;
    a free-text line is not. We emit one JSON object per line.

JAVA NOTE:
    This is the role of SLF4J + Logback with a JSON encoder, plus an MDC
    (Mapped Diagnostic Context) for per-request fields like a request id. We
    build a small version from the standard library so you can see exactly how
    it works.

PRODUCTION UPGRADE:
    For richer ergonomics (automatic context binding, processors) reach for
    `structlog`. The concepts below transfer directly.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any

# SECURITY: any log field whose (lowercased) key contains one of these tokens
#   is replaced with "***". This is defense-in-depth so a careless
#   `logger.info("...", extra={"api_key": key})` cannot leak a secret.
_REDACT_TOKENS = ("api_key", "authorization", "token", "secret", "password")
_REDACTED = "***"


def _redact(key: str, value: Any) -> Any:
    """Redact a value if its key looks sensitive."""
    lowered = key.lower()
    if any(token in lowered for token in _REDACT_TOKENS):
        return _REDACTED
    return value


# These are the attributes the stdlib attaches to every LogRecord. We skip them
# when collecting the user's `extra={...}` fields, keeping only custom data.
_STANDARD_LOGRECORD_ATTRS = set(vars(logging.makeLogRecord({})).keys()) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Format each log record as a single line of JSON.

    SYNTAX TIP: subclassing `logging.Formatter` and overriding `format` is the
        standard extension point of Python's logging framework — the analog of a
        custom Logback encoder.
    """

    def format(self, record: logging.LogRecord) -> str:
        # The base payload present on every line.
        payload: dict[str, Any] = {
            "timestamp": dt.datetime.fromtimestamp(record.created, tz=dt.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include any custom fields passed via `logger.info(msg, extra={...})`,
        # redacting anything that looks like a secret.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOGRECORD_ATTRS and not key.startswith("_"):
                payload[key] = _redact(key, value)

        # If an exception was logged, attach its formatted traceback.
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # `default=str` makes non-JSON-serializable values (e.g. datetimes,
        # UUIDs) fall back to their string form instead of crashing the logger.
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger.

    WHY configure the ROOT logger? Libraries and our own modules all create
        loggers via `logging.getLogger(__name__)`; configuring the root means a
        single place controls formatting and level for the whole process.

    GOTCHA: calling `basicConfig` twice is a no-op, so we configure handlers
        explicitly and replace any existing ones to stay idempotent (important
        when the app factory runs more than once in tests).
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    JAVA NOTE: the convention `logging.getLogger(__name__)` mirrors
        `LoggerFactory.getLogger(MyClass.class)` — the logger name reflects the
        module it lives in, which makes log filtering by component trivial.
    """
    return logging.getLogger(name)
