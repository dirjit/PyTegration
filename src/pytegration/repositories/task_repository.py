"""TaskRepository — async CRUD and queries for the tasks table.

LESSON: Module 5 (Persistence). See docs/05-persistence-sqlalchemy.md
LAYER:  repositories

DESIGN: every method takes the ORM objects it needs and uses the injected
    AsyncSession. The repository NEVER commits — transaction boundaries are owned
    by the request-scoped session dependency (see db/session.py). This keeps the
    unit of work in one place.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pytegration.db.models import TaskORM
from pytegration.domain.enums import TaskStatus


class TaskRepository:
    """Data access for tasks.

    SYNTAX TIP: the constructor stores the session on `self`. There is no `new`
        keyword in Python — you instantiate with `TaskRepository(session)`. Type
        hints on `__init__` params give you Java-like clarity about dependencies.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: TaskORM) -> TaskORM:
        """Persist a new task and return it with its generated id.

        SYNTAX TIP: `session.add()` stages the INSERT; `flush()` sends it to the
            database NOW (within the transaction) so the auto-generated `id` and
            server defaults are populated, without committing. `refresh()` reloads
            server-side defaults (created_at/updated_at) onto the object.
        """
        self._session.add(task)
        await self._session.flush()
        await self._session.refresh(task)
        return task

    async def get(self, task_id: int) -> TaskORM | None:
        """Return a task by id, or None if it does not exist.

        SYNTAX TIP: `session.get(Model, pk)` is the optimized primary-key lookup
            (it checks the identity map first). It returns None when not found —
            the repository reports absence; the service decides it's a 404.
        """
        return await self._session.get(TaskORM, task_id)

    async def list(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[TaskORM], int]:
        """Return a page of tasks plus the total count matching the filter.

        SYNTAX TIP: the `*` in the signature forces every following argument to be
            passed by KEYWORD (`list(status=..., limit=...)`). This prevents
            accidental positional mix-ups like swapping limit and offset — a small
            API-design safety win Java gets from named parameters/builders.
        """
        # Build a SELECT statement declaratively; `select(TaskORM)` is the 2.0 way.
        stmt = select(TaskORM)
        count_stmt = select(func.count()).select_from(TaskORM)

        if status is not None:
            stmt = stmt.where(TaskORM.status == status)
            count_stmt = count_stmt.where(TaskORM.status == status)

        # Newest first, then apply pagination window.
        stmt = stmt.order_by(TaskORM.created_at.desc()).limit(limit).offset(offset)

        rows = list((await self._session.scalars(stmt)).all())
        total = (await self._session.scalar(count_stmt)) or 0
        return rows, total

    async def delete(self, task: TaskORM) -> None:
        """Delete a task (the caller is responsible for fetching it first)."""
        await self._session.delete(task)
        await self._session.flush()
