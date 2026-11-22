"""Cosmos domain types — the building blocks of the Cosmic Explorer.

LESSON: Module 11 (Cosmic Explorer). See docs/11-cosmic-explorer.md
LAYER:  domain

WHAT IS THIS?
    v0.2 adds a second, kid-facing domain to PyTegration: a curated, read-only
    atlas of the universe. Its job is to give young explorers a *mental map* —
    "where am I, how big is it, how far is it, how long has that light been
    travelling?" — and to spark curiosity about space science careers.

WHY frozen dataclasses (and not ORM models)?
    The atlas is reference data that never changes at runtime. Immutable value
    objects are the honest model for that: no database, no sessions, no
    migrations, and they are trivially safe to share between concurrent requests.
    JAVA NOTE: `@dataclass(frozen=True)` ≈ a Java `record`. Tuples (not lists)
    keep even the collection fields immutable — the analog of `List.of(...)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ----- Physical constants -----------------------------------------------------
# SYNTAX TIP: underscores in numeric literals (`299_792.458`) are just visual
#   separators — the same feature as Java's `1_000_000`.
SPEED_OF_LIGHT_KM_S = 299_792.458
KM_PER_LIGHT_YEAR = 9_460_730_472_580.8
KM_PER_AU = 149_597_870.7  # astronomical unit: the average Earth-Sun distance
SECONDS_PER_YEAR = 365.25 * 24 * 3600
SUN_DIAMETER_KM = 1_392_700.0
EARTH_DIAMETER_KM = 12_742.0


class ObjectKind(str, Enum):
    """What sort of thing a catalog entry is."""

    STAR = "star"
    PLANET = "planet"
    DWARF_PLANET = "dwarf_planet"
    MOON = "moon"
    GALAXY = "galaxy"
    NEBULA = "nebula"
    BLACK_HOLE = "black_hole"
    SPACECRAFT = "spacecraft"


@dataclass(frozen=True)
class CelestialObject:
    """One thing in the sky (or in orbit) that a kid can explore.

    Distances are "from Earth". For planets, whose distance changes as both
    worlds orbit the Sun, we store the distance at (about) their CLOSEST approach
    and flag it with `distance_varies`. For very distant galaxies we store the
    LIGHT-TRAVEL distance — how far the light has travelled to reach us — which
    is what "you are seeing the past" is all about. (Space has stretched while
    that light travelled, so those galaxies are even farther away *now*.)
    """

    slug: str
    name: str
    kind: ObjectKind
    emoji: str
    color: str  # a hex colour the web page uses for this object's card
    tagline: str
    distance_km: float
    diameter_km: float
    fun_facts: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    distance_varies: bool = False
    # `None` means "not meaningful for this object" (e.g. you cannot stand on a galaxy).
    surface_gravity_g: float | None = None
    orbital_period_days: float | None = None  # one trip around the Sun
    day_length_hours: float | None = None  # sunrise to sunrise
    moons: int | None = None  # known moons (new ones keep being discovered!)
    sun_distance_au: float | None = None  # average distance from the Sun

    @property
    def light_seconds(self) -> float:
        """How long light from this object takes to reach Earth, in seconds."""
        return self.distance_km / SPEED_OF_LIGHT_KM_S

    @property
    def names(self) -> tuple[str, ...]:
        """Every name this object answers to (lower-case), for lookups."""
        return (self.slug.replace("-", " "), self.name.lower(), *self.aliases)


@dataclass(frozen=True)
class ZoomLevel:
    """One step of the "Cosmic Zoom": a nested ring of our cosmic address."""

    order: int
    slug: str
    title: str
    address_line: str  # how this level reads in "your cosmic address"
    emoji: str
    color: str
    size_km: float  # roughly how wide this level is
    analogy: str
    fun_fact: str
    contains: str  # what you find at this level


@dataclass(frozen=True)
class Milestone:
    """A moment in Earth's history, used by the Light Time Machine.

    Recent events carry a calendar `year` (so "years ago" stays correct as time
    passes); deep-time events carry a fixed `years_ago`.
    """

    text: str
    year: int | None = None
    years_ago: float | None = None


@dataclass(frozen=True)
class QuizQuestion:
    """A multiple-choice question with a kid-friendly explanation."""

    id: str
    topic: str
    prompt: str
    choices: tuple[str, ...]
    answer: str
    explanation: str


@dataclass(frozen=True)
class Career:
    """A real job in space science, with something a kid can try today."""

    slug: str
    title: str
    emoji: str
    what_they_do: str
    helpful_subjects: tuple[str, ...]
    try_this: str
