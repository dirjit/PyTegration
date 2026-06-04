"""Pure-Python domain entity — the framework-free view of a Task.

LESSON: Module 1 (Python for Java Devs). See docs/01-python-for-java-devs.md
LAYER:  domain

WHY does this exist when we already have an ORM model AND a Pydantic schema?
    To make the "three flavors of a class with fields" lesson concrete:
      - dataclass (here): plain business object, no framework — the POJO/record.
      - Pydantic schema:  validates external input/output (the API boundary).
      - SQLAlchemy ORM:   maps to a database table (persistence).
    In a small app you might not need all three; this project keeps the domain
    entity to show the *option* and the trade-offs. The service layer is free to
    work with whichever representation fits.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from pytegration.domain.enums import TaskPriority, TaskStatus


# SYNTAX TIP: `@dataclass` auto-generates `__init__`, `__repr__`, and `__eq__`
#   from the annotated fields. `frozen=True` makes instances immutable (fields
#   cannot be reassigned), and `slots=True` saves memory by skipping per-instance
#   __dict__. This is the closest Python equivalent to a Java `record`.
@dataclass(frozen=True, slots=True)
class Task:
    """An immutable snapshot of a task as the business domain sees it."""

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    created_at: dt.datetime
    updated_at: dt.datetime

    @property
    def is_open(self) -> bool:
        """A task is 'open' until it is DONE.

        WHY put this here? Business rules that are independent of HTTP and SQL
            belong on the domain entity, where they can be unit-tested without a
            web server or a database.
        """
        return self.status is not TaskStatus.DONE
