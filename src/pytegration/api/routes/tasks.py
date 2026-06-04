"""Task CRUD endpoints.

LESSON: Module 3 (API Design). See docs/03-api-design-fastapi.md
LAYER:  api

DESIGN: every handler is thin. It (1) receives validated input, (2) calls the
    TaskService, (3) returns a typed response. No business logic, no SQL. If a
    handler grows an `if`, that logic almost certainly belongs in the service.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from pytegration.api.deps import TaskServiceDep
from pytegration.domain.enums import TaskStatus
from pytegration.schemas.common import Page
from pytegration.schemas.task import TaskCreate, TaskRead, TaskUpdate

# `prefix` + `tags` group every route under /tasks and label it in the docs.
router = APIRouter(prefix="/tasks", tags=["tasks"])


# SYNTAX TIP: `status_code=201` sets the success status for creation. FastAPI
#   uses the return annotation (`-> TaskRead`) AND `response_model` to validate,
#   serialize, and document the body. JAVA NOTE: ≈ `@PostMapping` returning
#   `ResponseEntity.status(CREATED).body(dto)` but declarative.
@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
async def create_task(payload: TaskCreate, service: TaskServiceDep) -> TaskRead:
    """Create a new task. The request body is validated by `TaskCreate`."""
    # GOTCHA: `payload` is already validated by the time we get here. There is no
    #   need for manual null/format checks — that is Pydantic's job at the edge.
    return await service.create_task(payload)


@router.get("", response_model=Page[TaskRead], summary="List tasks")
async def list_tasks(
    service: TaskServiceDep,
    # SYNTAX TIP: `Annotated[Type, Query(...)]` declares a query-string parameter
    #   with validation and OpenAPI docs. (Putting `Query()` directly in the
    #   default is discouraged — the Annotated form is the modern FastAPI style.)
    #   `ge`/`le` bound the values, so a client cannot request a 10-million-row
    #   page (a denial-of-service guard, see Module 8).
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TaskRead]:
    """Return a paginated, optionally status-filtered list of tasks."""
    items, total = await service.list_tasks(status=status_filter, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


# SYNTAX TIP: `{task_id}` is a path parameter; FastAPI parses and validates it as
#   an int because of the `task_id: int` annotation on the handler.
@router.get("/{task_id}", response_model=TaskRead, summary="Get a task by id")
async def get_task(task_id: int, service: TaskServiceDep) -> TaskRead:
    """Return one task. Raises 404 (via NotFoundError) if it does not exist."""
    return await service.get_task(task_id)


@router.patch("/{task_id}", response_model=TaskRead, summary="Update a task")
async def update_task(task_id: int, payload: TaskUpdate, service: TaskServiceDep) -> TaskRead:
    """Apply a partial update (PATCH). Only the fields sent are changed."""
    return await service.update_task(task_id, payload)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
async def delete_task(task_id: int, service: TaskServiceDep) -> Response:
    """Delete a task. Returns 204 No Content on success, 404 if missing.

    WHY return an explicit `Response`? A 204 response must have NO body. Returning
        a bare `Response(status_code=204)` tells FastAPI exactly that, instead of
        trying to serialize a value into a forbidden body.
    """
    await service.delete_task(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
