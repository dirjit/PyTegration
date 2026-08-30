"""Domain enums: task status and priority.

LESSON: Module 1 (Python for Java Devs). See docs/01-python-for-java-devs.md
LAYER:  domain
"""

from __future__ import annotations

from enum import StrEnum


class TaskStatus(StrEnum):
    """Lifecycle state of a task.

    SYNTAX TIP: `StrEnum` (Python 3.11+) is a `str`-valued Enum: each member IS a
        real string, so it serializes to its value (`"todo"`) in JSON and the
        database automatically while still giving you typed constants in code.
        It replaces the older `class TaskStatus(str, Enum)` idiom and, unlike it,
        makes `str(TaskStatus.TODO) == "todo"` (not `"TaskStatus.TODO"`).
    JAVA NOTE: equivalent to a Java `enum TaskStatus { TODO, IN_PROGRESS, DONE }`,
        but the string values make persistence and API responses human-readable.
    """

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(StrEnum):
    """How urgent a task is.

    WHY model priority as an enum and not a free-form string? It makes invalid
        values impossible: Pydantic rejects anything outside this set at the API
        boundary, and your code can `match`/branch exhaustively.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
