# Module 8 — Security

> **Goal:** the security practices baked into this project, and how to harden
> further for production.

## Defense in depth — the layers

### 1. Authentication
API-key auth as a router-level dependency
([`core/security.py`](../src/pytegration/core/security.py)). Attaching it to the
`/api/v1` router protects **every** endpoint below it — you can't forget to guard
a new route. Health probes stay open for orchestrators.

```python
if provided_key is None or not secrets.compare_digest(provided_key, settings.api_key):
    raise AuthError("Missing or invalid API key.")
```

**Why `secrets.compare_digest` and not `==`?** A normal comparison short-circuits
at the first differing byte, leaking timing information an attacker can use to
guess the key byte-by-byte. `compare_digest` runs in **constant time**.

> **PRODUCTION UPGRADE:** swap the API key for OAuth2/OIDC JWTs. The dependency
> *shape* is identical — only the verification body changes. The Java analog is a
> Spring Security filter chain / `@PreAuthorize`.

### 2. Input validation
Every request body/query is a Pydantic model with `extra="forbid"` and bounds
(`min_length`, `ge`/`le`). This blocks **mass assignment** (unexpected fields) and
**unbounded inputs** (a 10-million-row page, a giant prompt). Validation is your
first line of defense — see [`schemas/`](../src/pytegration/schemas).

### 3. Rate limiting
A per-identity token-bucket middleware
([`core/middleware.py`](../src/pytegration/core/middleware.py)) caps request rate
and returns `429` with `Retry-After`. It throttles abuse and protects expensive
endpoints (the LLM agent above all).

> **PRODUCTION UPGRADE:** the limiter is in-memory (per-process). Behind a load
> balancer, store counters in Redis (e.g. `slowapi`) so the limit is shared.

### 4. Don't leak internals
- The catch-all exception handler logs the full error server-side but returns a
  generic message — no stack traces to clients
  ([`core/errors.py`](../src/pytegration/core/errors.py)).
- The logger redacts secret-looking fields (Module 9).
- CORS uses an explicit allow-list, never `*`; interactive docs are disabled in
  production (`Settings.docs_enabled`).

### 5. Supply chain & runtime
- Dependencies are **pinned** (`requirements*.txt`); CI runs `pip-audit`.
- The Docker image runs as a **non-root** user and excludes secrets via
  `.dockerignore`.

## LLM-specific security (prompt injection & tool safety)

Treat the model's output as **untrusted input**. The guardrails in
[`agent/tools.py`](../src/pytegration/agent/tools.py):

1. **Tool allow-list** — the model can only call a fixed registry of tools. There
   is no "run arbitrary code/SQL" tool, so the worst it can do is call an allowed
   tool with bad arguments.
2. **Argument re-validation** — every tool call's arguments are validated by a
   Pydantic model before execution, exactly like a hostile HTTP request.
3. **Same authority** — tools delegate to the same `TaskService` the API uses, so
   the agent can't exceed the caller's permissions.
4. **Loop/cost caps** — a hard `agent_max_iterations` bound stops runaway loops.
5. **Prompt-injection framing** — the system prompt tells the model to treat task
   content as data, not instructions
   ([`agent/prompts.py`](../src/pytegration/agent/prompts.py)). This is
   defense-in-depth and **imperfect by nature** — which is exactly why rules 1–3
   (the model simply has no dangerous tool) are the real protection.

➡️ Next: [Module 9 — Observability](09-observability.md)
