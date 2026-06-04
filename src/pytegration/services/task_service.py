"""TaskService — business logic for tasks, shared by the API and the AI agent.

LESSON: Module 4 (Layered Architecture). See docs/04-layered-architecture.md
LAYER:  services

WHY this is the most important file to get right:
    Both the HTTP routes (api/routes/tasks.py) AND the agent's tools
    (agent/tools.py) call THIS class. Because the rules live here once, the agent
    can never do something a normal API client couldn't — a key security property
    (see Module 10). The agent is just another caller of the same service.
"""

from __future__ import annotations

from pytegration.core.errors import NotFoundError
from pytegration.db.models import TaskORM
from pytegration.domain.enums import TaskStatus
from pytegration.repositories.task_repository import TaskRepository
from pytegration.schemas.task import TaskCreate, TaskRead, TaskUpdate


class TaskService:
    """Application operations for tasks.

    The service receives a repository (dependency injection) rather than creating
    one, so tests can pass a repository backed by an in-memory database.
    """

    def __init__(self, repository: TaskRepository) -> None:
        self._repo = repository

    async def create_task(self, payload: TaskCreate) -> TaskRead:
        """Create a new task (always starts in the TODO state)."""
        task = TaskORM(
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            status=TaskStatus.TODO,
        )
        saved = await self._repo.add(task)
        # SYNTAX TIP: `model_validate(orm_obj)` converts the ORM entity into the
        #   API DTO using `from_attributes=True` (set on TaskRead). This is the
        #   single, explicit place we cross the persistence -> API boundary.
        return TaskRead.model_validate(saved)

    async def get_task(self, task_id: int) -> TaskRead:
        """Return a task by id, or raise NotFoundError.

        WHY raise instead of returning None? The caller asked for a specific task;
            its absence is an exceptional outcome that should become a 404. The
            api layer translates this exception to HTTP (see core/errors.py).
        """
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} was not found.")
        return TaskRead.model_validate(task)

    async def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[TaskRead], int]:
        """Return a page of tasks plus the total count."""
        rows, total = await self._repo.list(status=status, limit=limit, offset=offset)
        # SYNTAX TIP: a list comprehension `[f(x) for x in xs]` is the idiomatic,
        #   readable way to transform a collection — the rough equivalent of a
        #   Java Stream `map(...).collect(toList())`, but built into the language.
        return [TaskRead.model_validate(row) for row in rows], total

    async def update_task(self, task_id: int, payload: TaskUpdate) -> TaskRead:
        """Apply a partial update (PATCH semantics) and return the result."""
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} was not found.")

        # SYNTAX TIP: `model_dump(exclude_unset=True)` returns ONLY the fields the
        #   client actually sent, so omitted fields are left unchanged — exactly
        #   the PATCH semantics we documented on TaskUpdate.
        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(task, field, value)  # apply each provided field to the ORM row

        # No explicit add() needed: `task` is already tracked by the session, so
        # the change is flushed/committed by the session dependency.
        await self._repo.add(task)  # add() also flushes+refreshes for updated_at
        return TaskRead.model_validate(task)

    async def delete_task(self, task_id: int) -> None:
        """Delete a task, or raise NotFoundError if it does not exist."""
        task = await self._repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} was not found.")
        await self._repo.delete(task)

    async def summarize_tasks(self) -> dict[str, object]:
        """Produce a compact, structured summary of all tasks.

        WHY a structured dict and not free text? This method powers BOTH a future
            reporting endpoint and an agent tool. Returning structured data lets
            the agent reason about it (and lets us test exact counts), rather than
            parsing prose. The LLM turns these numbers into a sentence for the user.
        """
        # Fetch a bounded window of tasks for the breakdown. (For very large data
        # sets you'd push these aggregations into SQL; kept simple for teaching.)
        rows, total = await self._repo.list(limit=100, offset=0)

        by_status: dict[str, int] = {s.value: 0 for s in TaskStatus}
        for row in rows:
            # `row.status` may be the enum or its raw string depending on load
            # path; normalise to the string key defensively.
            key = row.status.value if isinstance(row.status, TaskStatus) else str(row.status)
            by_status[key] = by_status.get(key, 0) + 1

        open_count = by_status[TaskStatus.TODO.value] + by_status[TaskStatus.IN_PROGRESS.value]
        return {
            "total": total,
            "by_status": by_status,
            "open": open_count,
        }
