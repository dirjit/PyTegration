"""Shared, reusable schemas: health, pagination, and the error envelope.

LESSON: Module 3 (API Design). See docs/03-api-design-fastapi.md
LAYER:  schemas
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# SYNTAX TIP: `TypeVar` declares a generic type variable. Combined with
#   `Generic[ItemT]` below it gives us Java-style generics: `Page[TaskRead]`.
ItemT = TypeVar("ItemT")


class HealthResponse(BaseModel):
    """Response body for the liveness/readiness endpoints."""

    status: str = Field(examples=["ok"])
    version: str


class ErrorResponse(BaseModel):
    """A consistent error envelope returned for every handled failure.

    WHY a single error shape? Clients should be able to parse ANY error the same
        way. We always return `{"error": {"code": ..., "message": ...}}` so a
        404 and a 422 look structurally identical to the caller.
    JAVA NOTE: this is the job of a `@ControllerAdvice` + a shared error DTO in
        Spring; see core/errors.py for where it is produced.
    """

    class _ErrorDetail(BaseModel):
        code: str
        message: str

    error: _ErrorDetail


class Page(BaseModel, Generic[ItemT]):
    """A generic paginated list response: `Page[TaskRead]`, `Page[...]`, etc.

    SYNTAX TIP: `class Page(BaseModel, Generic[ItemT])` makes Page parametric.
        Pydantic v2 fully understands these generics, so FastAPI can generate a
        precise OpenAPI schema for each concrete `Page[...]`.
    """

    # `model_config` with `frozen=True` makes instances immutable (like a Java
    # record). Responses are write-once, so immutability documents intent.
    model_config = ConfigDict(frozen=True)

    items: list[ItemT]
    total: int = Field(ge=0, description="Total number of items across all pages.")
    limit: int = Field(ge=1, le=100, description="Page size that was applied.")
    offset: int = Field(ge=0, description="Number of items skipped.")
