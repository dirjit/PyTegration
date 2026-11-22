"""CosmosCatalog — an in-memory, read-only repository over the curated atlas.

LESSON: Module 11 (Cosmic Explorer). See docs/11-cosmic-explorer.md
LAYER:  repositories

WHY is this still a "repository" when there's no database?
    The repository pattern is about hiding WHERE data comes from behind a small,
    intention-revealing interface (`get`, `find`, `list`). TaskRepository talks to
    SQLAlchemy; this one reads Python constants. Services don't know or care —
    which is exactly the point.
    JAVA NOTE: like a Spring `@Repository` backed by a `Map` instead of JPA.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from pytegration.domain.cosmos import (
    Career,
    CelestialObject,
    Milestone,
    ObjectKind,
    QuizQuestion,
    ZoomLevel,
)
from pytegration.repositories import cosmos_data


def _normalize(text: str) -> str:
    """Lower-case and squash punctuation/whitespace so 'The  Moon!' == 'the moon'."""
    return re.sub(r"[^a-z0-9*]+", " ", text.lower()).strip()


class CosmosCatalog:
    """Look things up in the atlas by slug, name or alias."""

    def __init__(
        self,
        objects: Iterable[CelestialObject] = cosmos_data.OBJECTS,
        zoom_levels: Iterable[ZoomLevel] = cosmos_data.ZOOM_LEVELS,
        milestones: Iterable[Milestone] = cosmos_data.MILESTONES,
        quiz: Iterable[QuizQuestion] = cosmos_data.QUIZ,
        careers: Iterable[Career] = cosmos_data.CAREERS,
    ) -> None:
        # WHY accept the data as arguments (with defaults)? Tests can build a
        #   catalog from a tiny hand-made data set — constructor injection again.
        self._objects = tuple(objects)
        self._zoom_levels = tuple(sorted(zoom_levels, key=lambda z: z.order))
        self._milestones = tuple(milestones)
        self._quiz = {q.id: q for q in quiz}
        self._careers = tuple(careers)

        # Build the name index ONCE. Every alias maps to its object.
        # SYNTAX TIP: a dict comprehension with two `for` clauses flattens
        #   "each object x each of its names" into one mapping.
        self._by_name: dict[str, CelestialObject] = {
            _normalize(name): obj for obj in self._objects for name in obj.names
        }
        # Longest names first, so "andromeda galaxy" wins over "andromeda" when
        # scanning free text, and "the moon" is matched as a whole phrase.
        self._names_longest_first = sorted(self._by_name, key=len, reverse=True)

    # ----- Objects -----------------------------------------------------------

    def list_objects(self, kind: ObjectKind | None = None) -> list[CelestialObject]:
        """All objects (optionally of one kind), in atlas order."""
        return [o for o in self._objects if kind is None or o.kind is kind]

    def find(self, name: str) -> CelestialObject | None:
        """Find an object by slug, name or alias (case/punctuation-insensitive)."""
        return self._by_name.get(_normalize(name))

    def find_mentions(self, text: str) -> list[CelestialObject]:
        """Return every object mentioned in free text, in order of appearance.

        Used by the offline mock guide to understand questions like
        "Is Jupiter bigger than Earth?". Matches whole words only, so "sun" does
        not match inside "Sunday".
        """
        haystack = f" {_normalize(text)} "
        found: list[tuple[int, CelestialObject]] = []
        taken: list[range] = []  # character spans already claimed by a longer name
        for name in self._names_longest_first:
            for match in re.finditer(rf" {re.escape(name)} ", haystack):
                span = range(match.start() + 1, match.end() - 1)
                if any(span.start in t or (span.stop - 1) in t for t in taken):
                    continue
                taken.append(span)
                found.append((match.start(), self._by_name[name]))
        found.sort(key=lambda pair: pair[0])

        # De-duplicate while keeping order (an object may be named twice).
        unique: list[CelestialObject] = []
        for _, obj in found:
            if obj not in unique:
                unique.append(obj)
        return unique

    # ----- Everything else ---------------------------------------------------

    def zoom_levels(self) -> list[ZoomLevel]:
        return list(self._zoom_levels)

    def milestones(self) -> list[Milestone]:
        return list(self._milestones)

    def quiz_questions(self) -> list[QuizQuestion]:
        return list(self._quiz.values())

    def quiz_question(self, question_id: str) -> QuizQuestion | None:
        return self._quiz.get(question_id)

    def careers(self) -> list[Career]:
        return list(self._careers)
