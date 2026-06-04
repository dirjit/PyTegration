"""Unit tests for TaskService over a real in-memory database.

LESSON: Module 7 (Testing). See docs/07-testing.md

These are 'sociable' unit tests: the service runs against a real (in-memory)
SQLAlchemy session and repository, so we test the actual SQL and mapping — not a
mock of the database. They are still fast and isolated thanks to conftest.py.
"""

from __future__ import annotations

import pytest

from pytegration.core.errors import NotFoundError
from pytegration.domain.enums import TaskPriority, TaskStatus
from pytegration.schemas.task import TaskCreate, TaskUpdate
from pytegration.services.task_service import TaskService


async def test_create_then_get_round_trips(task_service: TaskService) -> None:
    """A created task can be fetched back with server-managed fields populated."""
    created = await task_service.create_task(
        TaskCreate(title="Write docs", priority=TaskPriority.HIGH)
    )

    assert created.id > 0
    assert created.status is TaskStatus.TODO  # new tasks always start as TODO
    assert created.created_at is not None

    fetched = await task_service.get_task(created.id)
    assert fetched == created


async def test_get_missing_task_raises_not_found(task_service: TaskService) -> None:
    """Asking for a non-existent task is a domain-level NotFoundError (-> 404)."""
    with pytest.raises(NotFoundError):
        await task_service.get_task(9999)


async def test_update_applies_partial_changes_only(task_service: TaskService) -> None:
    """PATCH semantics: only provided fields change; the rest are untouched."""
    created = await task_service.create_task(
        TaskCreate(title="Original", description="keep me", priority=TaskPriority.LOW)
    )

    updated = await task_service.update_task(created.id, TaskUpdate(status=TaskStatus.IN_PROGRESS))

    assert updated.status is TaskStatus.IN_PROGRESS  # changed
    assert updated.title == "Original"  # unchanged
    assert updated.description == "keep me"  # unchanged


async def test_list_filters_by_status_and_reports_total(task_service: TaskService) -> None:
    """Listing supports a status filter and returns the matching total count."""
    a = await task_service.create_task(TaskCreate(title="todo-1"))
    await task_service.create_task(TaskCreate(title="todo-2"))
    await task_service.update_task(a.id, TaskUpdate(status=TaskStatus.DONE))

    done, done_total = await task_service.list_tasks(status=TaskStatus.DONE)
    assert done_total == 1
    assert [t.title for t in done] == ["todo-1"]

    everything, total = await task_service.list_tasks()
    assert total == 2


async def test_delete_removes_the_task(task_service: TaskService) -> None:
    """A deleted task can no longer be fetched."""
    created = await task_service.create_task(TaskCreate(title="temp"))
    await task_service.delete_task(created.id)

    with pytest.raises(NotFoundError):
        await task_service.get_task(created.id)


async def test_summarize_counts_open_tasks(task_service: TaskService) -> None:
    """The summary buckets tasks by status and computes the open count."""
    t1 = await task_service.create_task(TaskCreate(title="one"))
    await task_service.create_task(TaskCreate(title="two"))
    await task_service.update_task(t1.id, TaskUpdate(status=TaskStatus.DONE))

    summary = await task_service.summarize_tasks()

    assert summary["total"] == 2
    assert summary["open"] == 1  # one TODO remains, one is DONE
    assert summary["by_status"][TaskStatus.DONE.value] == 1
