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
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from pytegration import __version__
from pytegration.api.router import api_v1_router, public_v1_router, root_router
from pytegration.core.config import Settings, get_settings
from pytegration.core.errors import register_exception_handlers
from pytegration.core.logging import configure_logging, get_logger
from pytegration.core.middleware import RateLimitMiddleware, RequestContextMiddleware
from pytegration.db.session import create_engine, create_session_factory

logger = get_logger(__name__)

# The Cosmic Explorer web page ships INSIDE the package (see pyproject's
# package-data), so it works from an installed wheel / Docker image too.
WEB_DIR = Path(__file__).parent / "web"


class SecureStaticFiles(StaticFiles):
    """StaticFiles that adds browser security headers to every file it serves.

    SECURITY: a strict Content-Security-Policy means the page may only load
        scripts, styles and data from THIS server — no third-party trackers or
        CDNs (a children's page should have none), and injected inline scripts
        won't run. `nosniff` stops browsers guessing content types.
    JAVA NOTE: like adding headers in a Spring `ResourceHttpRequestHandler`
        or a servlet filter scoped to /static/**.
    """

    CSP = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'self'"
    )

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Content-Security-Policy"] = self.CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


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
        summary="Teaching-grade Task Manager API + Claude agent + Cosmic Explorer for kids.",
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
    # GOTCHA (ordering): `add_middleware` PREPENDS, so the LAST one added is the
    #   OUTERMOST (runs first on the way in). We add them so the processing order
    #   is: RequestContext -> RateLimit -> CORS -> routes. That way every log line
    #   (including rate-limit rejections) already carries the request id.

    # Innermost: CORS. SECURITY: restricted to an explicit allow-list from
    # settings, never "*" (a wildcard origin with credentials is a known footgun).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Middle: per-identity rate limiting.
    app.add_middleware(
        RateLimitMiddleware,
        capacity=settings.rate_limit_capacity,
        window_seconds=settings.rate_limit_window_seconds,
    )
    # Outermost: request id + access logging.
    app.add_middleware(RequestContextMiddleware)

    # ----- Error handling ----------------------------------------------------
    # Translate domain exceptions into the standard JSON error envelope.
    register_exception_handlers(app)

    # ----- Routes ------------------------------------------------------------
    app.include_router(root_router)  # /health, /ready
    app.include_router(api_v1_router)  # /api/v1/... (API key required)
    app.include_router(public_v1_router)  # /api/v1/cosmos/... (public, read-only)

    # ----- Cosmic Explorer web page (v0.2) ----------------------------------
    # `html=True` serves index.html for "/explore/". The page is plain HTML/CSS/JS
    # that calls the public /api/v1/cosmos endpoints — no build step, no npm.
    app.mount("/explore", SecureStaticFiles(directory=WEB_DIR, html=True), name="explore")

    @app.get("/", include_in_schema=False)
    async def _home() -> RedirectResponse:
        """Send visitors at the site root straight to the explorer page."""
        return RedirectResponse(url="/explore/")

    return app


# The module-level ASGI app object that `uvicorn pytegration.main:app` serves.
app = create_app()
