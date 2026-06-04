"""ORM models — how domain data is mapped to database tables.

LESSON: Module 5 (Persistence). See docs/05-persistence-sqlalchemy.md
LAYER:  db

JAVA NOTE:
    `TaskORM` is a JPA `@Entity`. `Mapped[...]` + `mapped_column(...)` together
    play the role of `@Column`, and the class attribute `__tablename__` is
    `@Table(name=...)`. SQLAlchemy's `Session` is the `EntityManager`.

WHY a separate `*ORM` name?
    We deliberately suffix the persistence class so it is never confused with the
    Pydantic API schema (`TaskRead`) or a future domain entity (`Task`). Three
    distinct shapes, three distinct names — see schemas/__init__.py for why.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from pytegration.db.base import Base
from pytegration.domain.enums import TaskPriority, TaskStatus


class TaskORM(Base):
    """A task row in the `tasks` table."""

    __tablename__ = "tasks"

    # SYNTAX TIP: `Mapped[int]` is the *typed* column declaration. The annotation
    #   tells mypy the Python type; `mapped_column(...)` configures the SQL side.
    #   `primary_key=True` makes this the surrogate key (auto-incrementing).
    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # SYNTAX TIP: `Mapped[str | None]` (note the `| None`) maps to a NULLABLE
    #   column. The type hint and the database constraint stay in sync — change
    #   one and mypy nudges you about the other.
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # WHY store the enum's value as a string column? Using `String` + the enum's
    #   string values keeps the DB human-readable and avoids native-ENUM
    #   portability issues across engines. The Python attribute is still typed as
    #   the enum, so the boundary stays type-safe.
    # `index=True` creates a database index on this column. WHY? We frequently
    #   filter tasks by status (e.g. "show me everything still TODO"); an index
    #   makes that lookup fast instead of a full table scan.
    status: Mapped[TaskStatus] = mapped_column(
        String(20), nullable=False, default=TaskStatus.TODO, index=True
    )
    priority: Mapped[TaskPriority] = mapped_column(
        String(20), nullable=False, default=TaskPriority.MEDIUM
    )

    # WHY set timestamps in the DATABASE (`server_default=func.now()`)? It makes
    #   the value authoritative and consistent regardless of which app server
    #   wrote the row. `onupdate` refreshes `updated_at` on every UPDATE.
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        # SYNTAX TIP: `__repr__` controls the debug string of an object — the
        #   analog of Java's `toString()`. Helpful in logs and test failures.
        return f"TaskORM(id={self.id!r}, title={self.title!r}, status={self.status!r})"
