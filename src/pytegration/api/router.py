"""Top-level API router — aggregates every resource router under one prefix.

LESSON: Module 3 / Module 4. See docs/03-api-design-fastapi.md
LAYER:  api

WHY a single aggregating router?
    `main.py` includes exactly one router and stays clean. Adding a new resource
    is a one-line change here, not an edit to the app factory. Versioning
    (`/api/v1`) lives in one place, so bumping to v2 later is trivial.
"""

from __future__ import annotations

from fastapi import APIRouter

from pytegration.api.routes import health, tasks

# Health checks live at the root (no version prefix) so probes hit /health.
root_router = APIRouter()
root_router.include_router(health.router)

# Versioned business endpoints live under /api/v1. The agent router is added
# here in a later slice.
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(tasks.router)
