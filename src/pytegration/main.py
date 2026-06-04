"""Application entry point — the FastAPI app factory and composition root.

LESSON: Module 3 (API Design). See docs/03-api-design-fastapi.md
LAYER:  api (composition root). This is where every piece is wired together:
        settings, logging, middleware, error handlers, and routers.

JAVA NOTE:
    `create_app()` is the equivalent of a Spring `@Configuration` class plus the
    `main()` that boots the context. The "composition root" is the single place
    where concrete implementations are assembled — keeping wiring out of the
    business code makes the rest of the app easy to test in isolation.

HOW IT RUNS:
    `uvicorn pytegration.main:app` imports this module, finds the `app` object,
    and serves it. `app` is created once at import time by calling the factory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pytegration import __version__
from pytegration.api.router import api_v1_router, root_router
from pytegration.core.config import Settings, get_settings
from pytegration.core.errors import register_exception_handlers
from pytegration.core.logging import configure_logging, get_logger
from pytegration.db.session import create_engine, create_session_factory

logger = get_logger(__name__)


# SYNTAX TIP: `@asynccontextmanager` turns a generator into an async context
#   manager. FastAPI calls it once on startup (code before `yield`) and once on
#   shutdown (code after `yield`). This replaced the older @app.on_event hooks.
#   JAVA NOTE: this is your `@PostConstruct` / `@PreDestroy` lifecycle, but for
#   the whole application rather than a single bean.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup and shutdown logic around the app's serving lifetime.

    WHY create the engine HERE rather than at import time? The database engine
        owns a connection pool — a real resource. Creating it on startup and
        disposing it on shutdown ties its lifetime to the app's, and lets tests
        spin up isolated apps without leaking connections.
    """
    settings: Settings = app.state.settings
    logger.info("application starting", extra={"app_env": settings.app_env.value})

    engine = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)

    yield

    # SYNTAX TIP: code after `yield` runs on shutdown. Disposing the engine closes
    #   every pooled connection cleanly — the analog of closing a Hikari pool.
    await engine.dispose()
    logger.info("application shutting down")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return a fully wired FastAPI application.

    WHY a factory function instead of a module-level `app = FastAPI()`?
        A factory lets tests construct an app with *overridden* settings (e.g. an
        in-memory database) without monkey-patching globals. It is the key to
        fast, isolated integration tests (see tests/conftest.py).

    Args:
        settings: optional override; defaults to the process-wide singleton.

    Returns:
        A configured FastAPI instance ready to serve.
    """
    # SYNTAX TIP: `settings or get_settings()` uses Python truthiness — if the
    #   caller passed None (falsy), fall back to the singleton. Concise, idiomatic.
    settings = settings or get_settings()

    configure_logging()

    app = FastAPI(
        title="PyTegration",
        version=__version__,
        summary="Teaching-grade Task Manager API + Claude agent.",
        lifespan=lifespan,
        # SECURITY: disable interactive docs and the OpenAPI schema in production
        #   so the full API surface is not advertised publicly.
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    # Stash settings on app.state so lifespan and dependencies can reach them.
    app.state.settings = settings

    # ----- Middleware --------------------------------------------------------
    # SECURITY: CORS is restricted to an explicit allow-list from settings, never
    #   "*". `allow_credentials=True` with a wildcard origin is a known footgun
    #   the browser will reject anyway.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ----- Error handling ----------------------------------------------------
    # Translate domain exceptions into the standard JSON error envelope.
    register_exception_handlers(app)

    # ----- Routes ------------------------------------------------------------
    app.include_router(root_router)  # /health, /ready
    app.include_router(api_v1_router)  # /api/v1/...

    return app


# The module-level ASGI app object that `uvicorn pytegration.main:app` serves.
app = create_app()
