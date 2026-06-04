"""Alembic migration environment — wires migrations to the app's async engine.

LESSON: Module 5 (Persistence). See docs/05-persistence-sqlalchemy.md

WHAT THIS FILE DOES:
    Alembic imports this module whenever you run `alembic upgrade`/`downgrade`/
    `revision --autogenerate`. It must tell Alembic (a) the database URL and
    (b) the target metadata (so autogenerate can diff models vs. the live DB).

JAVA NOTE:
    Think of this as the small bootstrap that hands Flyway your DataSource and
    points it at the migration scripts — except here we also expose the ORM
    metadata so Alembic can DRAFT migrations by comparing models to the schema.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from pytegration.core.config import get_settings

# IMPORTANT: importing the models module (`pytegration.db.models`) registers every
# ORM class on `Base.metadata` as a side effect. Without it, autogenerate would
# see an empty schema. `noqa: F401` silences the "imported but unused" warning.
from pytegration.db import models as _models  # noqa: F401
from pytegration.db.base import Base
from pytegration.db.session import create_engine

# Alembic's Config object provides access to values in alembic.ini.
config = context.config

# Configure Python logging from the .ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata Alembic compares against when autogenerating migrations.
target_metadata = Base.metadata

# Single source of truth for the URL: the application Settings.
_settings = get_settings()


def _run_migrations(connection: Connection) -> None:
    """Configure the migration context on a live connection and run it."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # `render_as_batch` lets SQLite (which lacks full ALTER TABLE) perform
        # column changes via the table-rebuild trick. Harmless on other engines.
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    """Open the async engine and run migrations within a sync-bridged connection."""
    engine = create_engine(_settings)
    # SYNTAX TIP: `run_sync` bridges Alembic's synchronous migration API onto our
    #   ASYNC engine — it runs the given sync function using the async connection.
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a DB connection (`alembic upgrade --sql`)."""
    context.configure(
        url=_settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database using the async engine."""
    asyncio.run(_run_async_migrations())


# Alembic decides which mode to use based on how it was invoked.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
