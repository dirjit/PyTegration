"""Async database engine, session factory, and the session DI dependency.

LESSON: Module 2 / Module 5. See docs/05-persistence-sqlalchemy.md
LAYER:  db

JAVA NOTE:
    The `engine` is the connection pool (like a Hikari `DataSource`). The
    `async_sessionmaker` is a factory of `AsyncSession`s, each one a short-lived
    "unit of work" — the equivalent of an `EntityManager` scoped to a request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pytegration.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the async SQLAlchemy engine (connection pool) from settings.

    WHY async? Database I/O is the classic place where a server spends most of
        its time waiting. An async engine lets the event loop serve other
        requests during that wait instead of blocking a thread (see Module 2).
    """
    # `pool_pre_ping` quietly checks a connection is alive before handing it out,
    # avoiding "server closed the connection" errors after idle periods.
    return create_async_engine(settings.database_url, pool_pre_ping=True, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the session factory bound to an engine.

    SYNTAX TIP: `expire_on_commit=False` keeps ORM objects usable AFTER the
        transaction commits. Without it, accessing an attribute post-commit would
        trigger a lazy reload — which fails once the async session is closed.
    """
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def get_session_from_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a session that commits on success and rolls back on error.

    SYNTAX TIP: this is an async GENERATOR used as a dependency. FastAPI runs the
        code up to `yield` before the request, injects the yielded value, then
        runs the code after `yield` once the response is sent. It is the
        "open a unit of work, then close it" pattern as a coroutine.

    WHY commit/rollback here? Centralizing transaction boundaries means individual
        repository/service methods never have to remember to commit — they just
        do work, and the request either fully succeeds or fully rolls back.
        JAVA NOTE: this is exactly what Spring's `@Transactional` does around a
        method; here it wraps the whole request explicitly and visibly.
    """
    # SYNTAX TIP: `async with` is the async form of `try/finally`-style resource
    #   management — it guarantees the session is closed even on error.
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            # GOTCHA: a bare `raise` re-raises the CURRENT exception with its
            #   original traceback intact. Do NOT write `raise e` — that resets
            #   the traceback and hides where the error really came from.
            raise
