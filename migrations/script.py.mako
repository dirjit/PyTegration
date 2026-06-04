"""${message}

Revision ID: ${up_revision}
Revises:${" " + down_revision if down_revision else ""}
Create Date: ${create_date}

LESSON: Module 5 (Persistence). Each migration has an `upgrade()` (apply) and a
`downgrade()` (revert) so schema changes are reversible and reviewable.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Revision identifiers used by Alembic to order migrations.
revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
