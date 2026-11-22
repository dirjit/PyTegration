"""Cosmic Explorer API contracts — response/request DTOs for /api/v1/cosmos.

LESSON: Module 11 (Cosmic Explorer). See docs/11-cosmic-explorer.md
LAYER:  schemas

WHY separate DTOs from the domain dataclasses (again)?
    The domain keeps raw numbers; the API adds kid-ready labels ("8 minutes 19
    seconds") and hides internals (aliases, the quiz answer!). Decoupling them
    means we can reword the page without touching the maths, and vice versa.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from pytegration.domain.cosmos import ObjectKind


class _Out(BaseModel):
    """Base for read-only responses (immutable once built)."""

    model_config = ConfigDict(frozen=True)


class LightTravelOut(_Out):
    seconds: float = Field(description="How long the light took to reach Earth.")
    label: str = Field(examples=["8 minutes 19 seconds"])
    left_in_year: int | None = Field(description="Calendar year the light set off (recent only).")
    before_event: str | None = Field(description="An Earth event that happened while it travelled.")
    message: str


class CelestialObjectOut(_Out):
    slug: str
    name: str
    kind: ObjectKind
    emoji: str
    color: str
    tagline: str
    fun_facts: list[str]
    distance_km: float
    distance_label: str
    distance_varies: bool
    diameter_km: float
    diameter_label: str
    earths_across: float = Field(description="How many Earths would fit across it.")
    surface_gravity_g: float | None
    orbital_period_days: float | None
    day_length_hours: float | None
    moons: int | None
    light: LightTravelOut


class ZoomLevelOut(_Out):
    order: int
    slug: str
    title: str
    address_line: str
    emoji: str
    color: str
    size_km: float
    size_label: str
    light_crossing: str = Field(description="How long light takes to cross this level.")
    contains: str
    analogy: str
    fun_fact: str


class CareerOut(_Out):
    slug: str
    title: str
    emoji: str
    what_they_do: str
    helpful_subjects: list[str]
    try_this: str


class AtlasOut(_Out):
    """Everything the explorer page needs in ONE request (fewer round trips)."""

    zoom_levels: list[ZoomLevelOut]
    objects: list[CelestialObjectOut]
    careers: list[CareerOut]


class WeightOut(_Out):
    slug: str
    name: str
    emoji: str
    gravity_g: float
    weight: float
    jump_height_m: float


class AgeOut(_Out):
    slug: str
    name: str
    emoji: str
    age: float
    days_to_next_birthday: int


class ScaleItemOut(_Out):
    slug: str
    name: str
    emoji: str
    color: str
    size_cm: float
    looks_like: str
    distance_m: float
    steps: int


class ScaleModelOut(_Out):
    sun_diameter_cm: float
    items: list[ScaleItemOut]
    nearest_star_km: float = Field(description="Proxima Centauri's distance at the same scale.")
    nearest_star_message: str


class TravelLegOut(_Out):
    mode: str
    emoji: str
    speed_kmh: float
    label: str


class TravelOut(_Out):
    destination: str
    distance_label: str
    legs: list[TravelLegOut]


class CompareOut(_Out):
    a: str
    b: str
    diameter_ratio: float
    volume_ratio: float
    summary: str


class MoonPhaseOut(_Out):
    date: date
    name: str
    emoji: str
    illumination: float = Field(ge=0, le=1, description="Fraction of the Moon's face that's lit.")
    age_days: float
    tip: str


class QuizQuestionOut(_Out):
    """A question as sent to the browser.

    SECURITY: the correct answer is deliberately NOT a field here. The client
        must ask the server to check an answer, so peeking at the network tab
        doesn't reveal it. (Small stakes for a quiz — but it's the same "never
        trust the client with the secret" rule as for real apps.)
    """

    id: str
    topic: str
    prompt: str
    choices: list[str]


class QuizAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=64)
    choice: str = Field(min_length=1, max_length=200)


class QuizAnswerOut(_Out):
    correct: bool
    answer: str
    explanation: str
    points: int
