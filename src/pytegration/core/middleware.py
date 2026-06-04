"""HTTP middleware — request correlation IDs, access logging, and rate limiting.

LESSON: Module 8 / Module 9. See docs/09-observability.md
LAYER:  core

WHAT IS MIDDLEWARE?
    Code that wraps EVERY request: it runs before the route handler, can short-
    circuit the response, and runs again after. JAVA NOTE: this is a Servlet
    `Filter` / a Spring `HandlerInterceptor`.

PRODUCTION UPGRADE:
    The rate limiter here is in-memory, so each process has its own counters —
    fine for a single instance or for learning. Behind a load balancer you would
    store counters in Redis (e.g. via `slowapi`) so the limit is shared across
    all instances.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from pytegration.core.logging import get_logger, request_id_ctx
from pytegration.schemas.common import ErrorResponse

logger = get_logger("pytegration.access")

# Paths that should bypass correlation overhead and rate limiting (probes).
_EXEMPT_PATHS = frozenset({"/health", "/ready"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, expose it, and emit one structured access log line.

    The id is taken from an inbound `X-Request-ID` header if present (so a trace
    can span services), otherwise generated. It is stored in a ContextVar so all
    logs during the request include it (see core/logging.py), and echoed back in
    the response header for client-side correlation.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        # `set` returns a token we use to restore the previous value afterwards —
        # important so the ContextVar does not leak across requests.
        token = request_id_ctx.set(request_id)
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            # SECURITY: we log method/path/status/timing — never the body, which
            #   could contain secrets or personal data.
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Always restore the ContextVar, even if the handler raised.
            request_id_ctx.reset(token)


@dataclass
class _TokenBucket:
    """A classic token bucket: tokens regenerate over time up to a capacity.

    Each request costs one token; if none are available, the request is rejected.
    This smooths bursts while bounding the sustained rate.
    """

    capacity: float
    refill_per_second: float
    tokens: float = field(default=0.0)
    updated_at: float = field(default_factory=time.monotonic)

    def allow(self) -> bool:
        """Refill based on elapsed time, then try to spend one token."""
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.updated_at = now
        # `min(...)` caps the bucket at capacity so idle clients can't bank tokens.
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-identity in-memory rate limiting using a token bucket.

    Identity is the API key (so each key gets its own budget), falling back to the
    client IP for unauthenticated requests.
    """

    def __init__(self, app: object, capacity: int, window_seconds: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._capacity = float(capacity)
        # Refilling `capacity` tokens over the window gives the desired average rate.
        self._refill_per_second = capacity / window_seconds
        # GOTCHA: a plain dict grows unbounded as new identities appear. For a
        #   teaching app this is acceptable; production would use a TTL cache.
        self._buckets: dict[str, _TokenBucket] = {}

    def _identity(self, request: Request) -> str:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key}"
        client = request.client
        return f"ip:{client.host}" if client else "ip:unknown"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        identity = self._identity(request)
        bucket = self._buckets.get(identity)
        if bucket is None:
            # New identities start with a full bucket (allowed an initial burst).
            bucket = _TokenBucket(
                capacity=self._capacity,
                refill_per_second=self._refill_per_second,
                tokens=self._capacity,
            )
            self._buckets[identity] = bucket

        if not bucket.allow():
            logger.warning("rate_limited", extra={"path": request.url.path})
            body = ErrorResponse(
                error={"code": "rate_limited", "message": "Too many requests."}
            ).model_dump()
            # SECURITY/UX: `Retry-After` tells well-behaved clients when to retry.
            return JSONResponse(status_code=429, content=body, headers={"Retry-After": "1"})

        return await call_next(request)
