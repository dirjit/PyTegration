"""Top-level API router — aggregates every resource router under one prefix.

LESSON: Module 3 / Module 4. See docs/03-api-design-fastapi.md
LAYER:  api

WHY a single aggregating router?
    `main.py` includes exactly one router and stays clean. Adding a new resource
    is a one-line change here, not an edit to the app factory. Versioning
    (`/api/v1`) lives in one place, so bumping to v2 later is trivial.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pytegration.api.routes import agent, health, tasks
from pytegration.core.security import require_api_key

# Health checks live at the root (no version prefix) so probes hit /health.
# SECURITY: these stay UNAUTHENTICATED so orchestrators/load balancers can probe.
root_router = APIRouter()
root_router.include_router(health.router)

# Versioned business endpoints live under /api/v1.
# SECURITY: attaching `require_api_key` at the ROUTER level protects every route
#   below it in one place — you cannot forget to guard a new endpoint. The agent
#   router (added later) inherits the same protection automatically.
api_v1_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
api_v1_router.include_router(tasks.router)
api_v1_router.include_router(agent.router)
