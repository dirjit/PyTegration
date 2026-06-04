"""Application exception types and the FastAPI handlers that render them.

LESSON: Module 9 (Observability). See docs/09-observability.md
LAYER:  core

WHY custom exception types?
    Lower layers (services, repositories) should signal failures in DOMAIN terms
    ("this task was not found"), NOT in HTTP terms ("404"). Only the api layer
    knows about HTTP. We define plain exceptions here and translate them to HTTP
    responses in one place, so business code never imports FastAPI.
    JAVA NOTE: the exceptions are your domain exceptions; the handlers below are
    a `@ControllerAdvice` / `@ExceptionHandler` that map them to status codes.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pytegration.core.logging import get_logger
from pytegration.schemas.common import ErrorResponse

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for all expected, handled application errors.

    SYNTAX TIP: subclassing `Exception` is how you define a custom exception in
        Python — there are no checked exceptions, so nothing forces a caller to
        handle it; our handlers catch it centrally instead.
    """

    # Subclasses set these. `status_code` is the HTTP status the api layer uses;
    # `code` is a stable, machine-readable string for clients.
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    """A requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationError(AppError):
    """A request was syntactically valid but violated a business rule."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class AuthError(AppError):
    """Authentication failed (missing or invalid credentials)."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class RateLimitError(AppError):
    """The caller exceeded their allowed request rate."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class AgentError(AppError):
    """The AI agent could not complete the request (e.g. provider failure)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "agent_error"


def _error_body(code: str, message: str) -> dict[str, object]:
    """Build the standard error envelope as a plain dict for JSONResponse."""
    return ErrorResponse(error={"code": code, "message": message}).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that convert exceptions into the standard error envelope.

    WHY centralize? Every error — ours, validation, or unexpected — leaves the
        API in the SAME JSON shape `{"error": {"code", "message"}}`. Clients get
        one predictable contract; we get one place to log failures.
    """

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        # Expected errors are logged at WARNING — they are part of normal operation.
        # GOTCHA: never put `message` (or other reserved LogRecord attribute names
        #   like `args`, `name`, `levelname`) in `extra={...}` — the stdlib logger
        #   raises KeyError on the collision. We use `detail` instead.
        logger.warning("app_error", extra={"code": exc.code, "detail": exc.message})
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI raises this when request data fails Pydantic validation. We
        # reshape its detail list into our envelope for a consistent client view.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("validation_error", "Request validation failed."),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # SECURITY: never leak internal exception text/stack traces to clients.
        #   We log the full detail server-side (exc_info=True) but return a
        #   generic message. `exc_info=True` attaches the traceback to the log.
        logger.error("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "An unexpected error occurred."),
        )
