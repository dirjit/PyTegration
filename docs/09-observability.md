# Module 9 — Observability

> **Goal:** make the running app explain itself — structured logs, request
> correlation, and consistent error responses.

## Structured (JSON) logging

In production, logs are consumed by machines (Datadog, CloudWatch, Loki). A JSON
object per line is queryable; free text is not. See
[`core/logging.py`](../src/pytegration/core/logging.py):

```json
{"timestamp":"...","level":"INFO","logger":"pytegration.access","message":"request",
 "method":"GET","path":"/api/v1/tasks","status_code":200,"duration_ms":3.1,
 "request_id":"a1b2c3..."}
```

We build a small `logging.Formatter` subclass from the standard library so you can
see exactly how it works. The Java analog is Logback with a JSON encoder.

> **PRODUCTION UPGRADE:** `structlog` adds ergonomics (context binding,
> processors). The concepts are identical.

## Secret redaction

The formatter redacts any log field whose key looks sensitive (`api_key`,
`authorization`, `token`, `secret`, `password`) → `"***"`. Defense-in-depth so a
careless `logger.info(..., extra={"api_key": key})` can't leak a secret. We also
**never log request bodies**.

**GOTCHA:** never put reserved `LogRecord` attribute names (`message`, `args`,
`name`, `levelname`, …) in `extra={...}` — the stdlib logger raises `KeyError`.
We use keys like `detail` instead.

## Request correlation (the MDC pattern)

Every request gets an id, stored in a `ContextVar`
([`core/middleware.py`](../src/pytegration/core/middleware.py)):

- Taken from an inbound `X-Request-ID` header if present (so a trace can span
  services), else generated.
- A `ContextVar` is async-safe, per-task state — the right tool so concurrent
  requests don't clobber each other's id. This is SLF4J's **MDC**.
- The formatter reads it, so **every** log line during a request carries its
  `request_id`. The id is also echoed in the response header for the client.

```python
token = request_id_ctx.set(request_id)
try:
    response = await call_next(request)
finally:
    request_id_ctx.reset(token)   # always restore — no leakage between requests
```

## Consistent error envelope

All errors — domain, validation, or unexpected — leave the API in the **same**
shape via centralized handlers ([`core/errors.py`](../src/pytegration/core/errors.py)):

```json
{"error": {"code": "not_found", "message": "Task 42 was not found."}}
```

This is Spring's `@ControllerAdvice`. Clients parse one structure for every
failure; you log failures in one place. Domain exceptions (`NotFoundError`,
`AuthError`, `RateLimitError`, …) carry their own HTTP status and stable `code`.

➡️ Next: [Module 10 — Agentic / LLM Integration](10-agentic-llm.md)
