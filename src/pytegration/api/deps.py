"""Dependency-injection providers — the wiring between layers, for FastAPI.

LESSON: Module 3 / Module 4. See docs/03-api-design-fastapi.md
LAYER:  api

WHAT IS A "DEPENDENCY" IN FASTAPI?
    A function whose return value FastAPI injects into a route (or another
    dependency) when you write `param: T = Depends(provider)`. FastAPI builds the
    whole graph per request and cleans it up afterwards.
    JAVA NOTE: this is Spring's IoC container, but explicit and per-request. There
    is no classpath scanning or `@Autowired` magic — you can read the wiring right
    here, which is exactly why it is easy to test (just call with fakes).

WHY a `Annotated[T, Depends(...)]` type alias for each dependency?
    It lets routes write `service: TaskServiceDep` instead of repeating
    `Depends(get_task_service)` everywhere — concise and DRY.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from pytegration.core.config import Settings
from pytegration.db.session import get_session_from_factory
from pytegration.repositories.task_repository import TaskRepository
from pytegration.services.task_service import TaskService


def get_settings_dep(request: Request) -> Settings:
    """Return the app's Settings (stashed on app.state by the factory).

    WHY read from `app.state` instead of calling get_settings()? It honors any
        override a test passed to `create_app(settings=...)`, so tests can run
        with a fully custom configuration.
    """
    settings: Settings = request.app.state.settings
    return settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide a request-scoped database session (commit/rollback handled).

    SYNTAX TIP: `async for ... yield` delegates to the async generator in
        db/session.py, re-exposing its single yielded session as a dependency.
        The transaction is committed or rolled back when the request finishes.
    """
    factory = request.app.state.session_factory
    async for session in get_session_from_factory(factory):
        yield session


# SYNTAX TIP: `Annotated[X, Depends(f)]` binds a type to its provider once, so
#   routes annotate parameters with these aliases instead of repeating Depends.
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_task_service(session: SessionDep) -> TaskService:
    """Build a TaskService for this request from the injected session."""
    return TaskService(TaskRepository(session))


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
