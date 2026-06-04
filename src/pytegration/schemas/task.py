"""Task API contracts — the request/response DTOs for the tasks resource.

LESSON: Module 1 / Module 3. See docs/03-api-design-fastapi.md
LAYER:  schemas

WHY separate Create / Update / Read models for ONE resource?
    Each direction has different rules:
      - TaskCreate: what a client may SEND to create (no id, no timestamps).
      - TaskUpdate: every field optional (PATCH semantics — change only some).
      - TaskRead:   what we RETURN (includes server-managed id + timestamps).
    Bundling these into one model would force nullable ids and let clients try to
    set timestamps. Distinct models make each contract precise and safe.
    JAVA NOTE: this is the request-DTO / response-DTO split you'd hand-roll (or
    generate with MapStruct) in a Spring app.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from pytegration.domain.enums import TaskPriority, TaskStatus


class TaskBase(BaseModel):
    """Fields common to creating and reading a task.

    SYNTAX TIP: `model_config = ConfigDict(extra="forbid")` makes Pydantic REJECT
        any field it does not recognise. SECURITY: this blocks "mass assignment"
        — a client cannot sneak in unexpected keys hoping to set internal fields.
    """

    model_config = ConfigDict(extra="forbid")

    # SYNTAX TIP: `Field(...)` (literal Ellipsis) marks a REQUIRED field and lets
    #   us attach validation + OpenAPI metadata. `min_length`/`max_length` are
    #   enforced before our code ever runs — validation as a first line of defense.
    title: str = Field(min_length=1, max_length=200, examples=["Write integration tests"])
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority = TaskPriority.MEDIUM


class TaskCreate(TaskBase):
    """Request body for `POST /tasks`. A new task always starts as TODO, so
    status is intentionally NOT accepted here — the server owns that invariant."""


class TaskUpdate(BaseModel):
    """Request body for `PATCH /tasks/{id}` — every field is optional.

    WHY all-optional? PATCH means "update the fields I send, leave the rest". A
        field left out (None) is "don't change"; this is distinct from setting a
        value. The service layer applies only the fields that were provided.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None


class TaskRead(TaskBase):
    """Response body returned for a task (the full server view)."""

    # SYNTAX TIP: `from_attributes=True` lets Pydantic build this model from an
    #   ORM object's attributes (`TaskRead.model_validate(task_orm)`), not just a
    #   dict. It is the bridge from the SQLAlchemy entity to the API DTO.
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    status: TaskStatus
    created_at: dt.datetime
    updated_at: dt.datetime
