"""SQLAlchemy declarative base and table naming conventions.

LESSON: Module 5 (Persistence). See docs/05-persistence-sqlalchemy.md
LAYER:  db

JAVA NOTE:
    `Base` is the analog of a JPA `@MappedSuperclass` / the EntityManager's
    metadata registry: every ORM model inherits from it, and SQLAlchemy collects
    their table definitions into `Base.metadata` — which Alembic reads to
    generate migrations.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# WHY define naming conventions? Databases auto-name constraints/indexes
#   unpredictably, which makes migrations on different engines diverge. Fixing
#   the templates here means Alembic generates stable, portable names (and can
#   actually drop a constraint by name later).
#   JAVA NOTE: comparable to configuring Hibernate's physical naming strategy.
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models.

    SYNTAX TIP: in SQLAlchemy 2.0 you subclass `DeclarativeBase` (a class) rather
        than calling the old `declarative_base()` factory. This newer style is
        fully typed, so mypy understands your models' columns.
    """

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)
