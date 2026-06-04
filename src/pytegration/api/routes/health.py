"""Health endpoints — liveness and readiness probes.

LESSON: Module 3 (API Design). See docs/03-api-design-fastapi.md
LAYER:  api

WHY two endpoints?
    - /health  (liveness):  "is the process up?" Used by orchestrators to decide
                            whether to restart the container.
    - /ready   (readiness): "can it serve traffic?" In a fuller app this would
                            check the database/dependencies before accepting load.
    JAVA NOTE: these mirror Spring Boot Actuator's /actuator/health/liveness and
    /readiness probes.

SECURITY: health endpoints are intentionally UNAUTHENTICATED — Kubernetes and
    load balancers must reach them without credentials. Everything else in the
    API is gated by the API-key dependency.
"""

from __future__ import annotations

from fastapi import APIRouter

from pytegration import __version__
from pytegration.schemas.common import HealthResponse

# SYNTAX TIP: `APIRouter` groups related endpoints, like a Spring
#   `@RequestMapping` at the controller level. We compose routers in
#   api/router.py, keeping each file focused on one resource.
router = APIRouter(tags=["health"])


# SYNTAX TIP: `@router.get(...)` is a decorator that registers the function
#   below as a GET handler. `response_model=HealthResponse` tells FastAPI to
#   validate and document the response shape (and strip any extra fields).
#   JAVA NOTE: this is `@GetMapping("/health")` returning a typed body.
@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    """Return 200 if the process is alive."""
    # SYNTAX TIP: `async def` makes this a coroutine. Even though this handler
    #   does no awaiting, FastAPI runs async and sync handlers seamlessly; we use
    #   async consistently so the style matches the database-backed routes.
    return HealthResponse(status="ok", version=__version__)


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def ready() -> HealthResponse:
    """Return 200 if the app is ready to serve traffic.

    NOTE: kept simple here. A production readiness check would, for example,
        run `SELECT 1` against the database and verify the LLM provider is
        configured before reporting ready.
    """
    return HealthResponse(status="ready", version=__version__)
