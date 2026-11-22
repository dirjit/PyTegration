"""CosmosService — the maths behind the Cosmic Explorer, in kid-friendly words.

LESSON: Module 11 (Cosmic Explorer). See docs/11-cosmic-explorer.md
LAYER:  services

WHAT LIVES HERE?
    Every "how far / how big / how long / how heavy" calculation, plus the words
    that turn a raw number into something a 9-year-old can picture ("about 8
    minutes", "1.3 million Earths"). The REST routes AND the Space Guide agent's
    tools both call this one service, so a kid gets the same answer whichever way
    they ask — the same "one service, many front doors" rule TaskService follows.

WHY mostly pure functions?
    Nothing here touches I/O. Pure functions are the easiest code in the world to
    test (see tests/unit/test_cosmos_service.py): input in, number out.
    JAVA NOTE: think `final` utility methods on a stateless `@Service`.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime

from pytegration.core.errors import NotFoundError, ValidationError
from pytegration.domain.cosmos import (
    EARTH_DIAMETER_KM,
    KM_PER_AU,
    KM_PER_LIGHT_YEAR,
    SECONDS_PER_YEAR,
    SPEED_OF_LIGHT_KM_S,
    SUN_DIAMETER_KM,
    CelestialObject,
    Milestone,
    QuizQuestion,
)
from pytegration.repositories.cosmos_catalog import CosmosCatalog

# ----- Speeds used by the travel calculator (km per hour) ----------------------
TRAVEL_SPEEDS_KMH: tuple[tuple[str, str, float], ...] = (
    ("walking", "🚶", 5),
    ("car on a highway", "🚗", 100),
    ("jet plane", "✈️", 900),
    ("fastest spacecraft ever (Parker Solar Probe)", "🛰️", 690_000),
    ("light", "💡", SPEED_OF_LIGHT_KM_S * 3600),
)

# A kid's standing jump on Earth, in metres — used for "how high could you jump?".
EARTH_JUMP_M = 0.3
# A kid-sized step, in metres — used by the scale-model walk.
STEP_M = 0.6

# Everyday things, smallest first, for "the Earth would be the size of a ___".
_EVERYDAY_SIZES_CM: tuple[tuple[float, str], ...] = (
    (0.05, "a grain of sand"),
    (0.15, "a poppy seed"),
    (0.35, "a peppercorn"),
    (0.8, "a pea"),
    (1.6, "a marble"),
    (4.0, "a ping-pong ball"),
    (7.0, "a tennis ball"),
    (12.0, "a grapefruit"),
    (22.0, "a football"),
    (30.0, "a beach ball"),
    (120.0, "a big exercise ball"),
)

# A reference new moon (6 Jan 2000, 18:14 UTC) and the average lunar cycle length.
_REFERENCE_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=UTC)
SYNODIC_MONTH_DAYS = 29.530588853

_MOON_PHASES: tuple[tuple[str, str, str], ...] = (
    (
        "New Moon",
        "🌑",
        "The Moon is between us and the Sun — great night for spotting faint stars!",
    ),
    ("Waxing Crescent", "🌒", "Look west just after sunset for a thin smile of a Moon."),
    (
        "First Quarter",
        "🌓",
        "Half lit! Binoculars show craters along the line between light and dark.",
    ),
    ("Waxing Gibbous", "🌔", "Almost full and getting bigger every night."),
    ("Full Moon", "🌕", "Rises at sunset. Can you spot the dark 'seas' made of old lava?"),
    ("Waning Gibbous", "🌖", "Rises after dark and lights up the late-night sky."),
    (
        "Last Quarter",
        "🌗",
        "Half lit again — visible in the morning sky. Look up on your way to school!",
    ),
    ("Waning Crescent", "🌘", "A thin sliver before dawn. Soon it will be a New Moon again."),
)


# =============================================================================
# Kid-friendly number formatting
# =============================================================================


def format_number(value: float) -> str:
    """Turn big numbers into words a kid can read: 149600000 -> '149.6 million'."""
    magnitude = abs(value)
    for threshold, word in (
        (1e18, "quintillion"),
        (1e15, "quadrillion"),
        (1e12, "trillion"),
        (1e9, "billion"),
        (1e6, "million"),
    ):
        if magnitude >= threshold:
            # SYNTAX TIP: `:g` drops trailing zeros (149.6, not 149.60).
            return f"{value / threshold:.1f}".rstrip("0").rstrip(".") + f" {word}"
    if magnitude >= 100:
        return f"{value:,.0f}"
    if magnitude >= 1:
        return f"{value:,.1f}".rstrip("0").rstrip(".")
    return f"{value:.2g}"


def format_distance(km: float) -> str:
    """Pick sensible units: metres, km, or light-years."""
    if km < 1:
        return f"{format_number(km * 1000)} m"
    if km >= 0.1 * KM_PER_LIGHT_YEAR:
        light_years = km / KM_PER_LIGHT_YEAR
        unit = "light-year" if round(light_years, 1) == 1 else "light-years"
        return f"{format_number(light_years)} {unit}"
    return f"{format_number(km)} km"


def _plural(value: float, unit: str) -> str:
    return f"{format_number(value)} {unit}" + ("" if round(value, 1) == 1 else "s")


def format_duration(seconds: float) -> str:
    """Human words for a duration: '8 minutes 19 seconds', '4.2 years', '2.5 million years'."""
    if seconds < 1:
        return f"{seconds:.2g} seconds"
    if seconds < 60:
        return _plural(round(seconds, 1), "second")
    if seconds < 3600:
        minutes, secs = divmod(round(seconds), 60)
        return _plural(minutes, "minute") + (f" {_plural(secs, 'second')}" if secs else "")
    if seconds < 86_400:
        hours, rest = divmod(round(seconds / 60), 60)
        return _plural(hours, "hour") + (f" {_plural(rest, 'minute')}" if rest else "")
    if seconds < SECONDS_PER_YEAR:
        return _plural(round(seconds / 86_400, 1), "day")
    return _plural(seconds / SECONDS_PER_YEAR, "year")


def in_sentence(name: str) -> str:
    """'The Sun' -> 'the Sun', so names read naturally mid-sentence."""
    return "the " + name[4:] if name.startswith("The ") else name


def everyday_size(cm: float) -> str:
    """Name an everyday thing about this size: 0.27 cm -> 'a peppercorn'."""
    if cm < _EVERYDAY_SIZES_CM[0][0] / 2:
        return "a speck of dust"
    # Pick the everyday object whose size is closest on a log scale (what our
    # eyes judge: 2x bigger looks like the same "step" whether tiny or huge).
    return min(_EVERYDAY_SIZES_CM, key=lambda pair: abs(math.log(pair[0] / cm)))[1]


# =============================================================================
# Result records returned by the service (the api layer maps them to DTOs).
# =============================================================================


@dataclass(frozen=True)
class LightTravel:
    seconds: float
    label: str
    left_in_year: int | None
    before_event: str | None
    message: str


@dataclass(frozen=True)
class WorldWeight:
    obj: CelestialObject
    weight: float
    jump_height_m: float


@dataclass(frozen=True)
class WorldAge:
    obj: CelestialObject
    age: float
    days_to_next_birthday: int


@dataclass(frozen=True)
class ScaleItem:
    obj: CelestialObject
    size_cm: float
    looks_like: str
    distance_m: float
    steps: int


@dataclass(frozen=True)
class TravelLeg:
    mode: str
    emoji: str
    speed_kmh: float
    label: str


@dataclass(frozen=True)
class SizeComparison:
    a: CelestialObject
    b: CelestialObject
    diameter_ratio: float
    volume_ratio: float
    summary: str


@dataclass(frozen=True)
class MoonPhase:
    on: date
    name: str
    emoji: str
    illumination: float
    age_days: float
    tip: str


@dataclass(frozen=True)
class AnswerCheck:
    correct: bool
    answer: str
    explanation: str
    points: int


class CosmosService:
    """Calculations and kid-friendly explanations over the CosmosCatalog."""

    def __init__(self, catalog: CosmosCatalog, *, today: date | None = None) -> None:
        self._catalog = catalog
        # WHY inject "today"? Anything that depends on the clock is untestable
        #   unless you can pin the clock. Production passes None (= real today).
        self._today = today

    @property
    def catalog(self) -> CosmosCatalog:
        return self._catalog

    def today(self) -> date:
        return self._today or datetime.now(UTC).date()

    # ----- Lookups -----------------------------------------------------------

    def get_object(self, name: str) -> CelestialObject:
        """Find an object or raise NotFoundError with a helpful hint."""
        obj = self._catalog.find(name)
        if obj is None:
            examples = ", ".join(o.name for o in self._catalog.list_objects()[:6])
            raise NotFoundError(f"I don't know '{name}' yet. Try one of: {examples}...")
        return obj

    # ----- Light Time Machine ------------------------------------------------

    def _years_ago(self, milestone: Milestone) -> float:
        if milestone.year is not None:
            return float(self.today().year - milestone.year)
        return float(milestone.years_ago or 0)

    def light_travel(self, seconds: float, *, subject: str = "it") -> LightTravel:
        """Explain how old the light we see is, and what Earth was doing then."""
        label = format_duration(seconds)
        years = seconds / SECONDS_PER_YEAR

        if seconds < 0.5:
            return LightTravel(
                seconds=seconds,
                label=label,
                left_in_year=None,
                before_event=None,
                message=f"Light from {subject} reaches you almost instantly — in {label}.",
            )

        # The OLDEST milestone that is still YOUNGER than the light: that event
        # happened while this light was already on its way to us.
        younger = [m for m in self._catalog.milestones() if self._years_ago(m) < years]
        before = max(younger, key=self._years_ago, default=None)
        left_in_year = round(self.today().year - years) if years < 10_000 else None

        if years < 1:
            message = f"You see {subject} as it was {label} ago."
        elif before is not None:
            message = (
                f"The light from {subject} set off about {label} ago. "
                f"It was already on its way before {before.text}!"
            )
        else:
            message = f"The light from {subject} set off about {label} ago, around the year {left_in_year}."
        return LightTravel(
            seconds=seconds,
            label=label,
            left_in_year=left_in_year,
            before_event=before.text if before else None,
            message=message,
        )

    def light_travel_for(self, obj: CelestialObject) -> LightTravel:
        if obj.distance_km == 0:
            return LightTravel(
                seconds=0,
                label="0 seconds",
                left_in_year=None,
                before_event=None,
                message=f"You're right inside {in_sentence(obj.name)}!",
            )
        return self.light_travel(obj.light_seconds, subject=in_sentence(obj.name))

    def time_machine(self, light_years: float) -> LightTravel:
        """The slider version: 'a star N light-years away'."""
        if not 0 < light_years <= 13_800_000_000:
            raise ValidationError("Pick a distance between 0 and 13.8 billion light-years.")
        return self.light_travel(
            light_years * SECONDS_PER_YEAR,
            subject=f"a star {format_distance(light_years * KM_PER_LIGHT_YEAR)} away",
        )

    # ----- Space Gym ---------------------------------------------------------

    def _standable_worlds(self) -> list[CelestialObject]:
        return [o for o in self._catalog.list_objects() if o.surface_gravity_g is not None]

    def weight_on(self, obj: CelestialObject, earth_weight: float) -> WorldWeight:
        """Your weight there = your Earth weight x that world's surface gravity.

        Mass (how much "stuff" you are) never changes; weight (how hard a world
        pulls on that stuff) does. Units in = units out (kg-on-a-scale or lb).
        """
        if obj.surface_gravity_g is None:
            raise ValidationError(
                f"{obj.name} has no surface to stand on, so there's no weight to measure!"
            )
        return WorldWeight(
            obj=obj,
            weight=round(earth_weight * obj.surface_gravity_g, 1),
            jump_height_m=round(EARTH_JUMP_M / obj.surface_gravity_g, 2),
        )

    def weights(self, earth_weight: float) -> list[WorldWeight]:
        return [self.weight_on(o, earth_weight) for o in self._standable_worlds()]

    def ages(self, earth_years: float) -> list[WorldAge]:
        """How old you'd be on each world, and how long until your next birthday there."""
        results: list[WorldAge] = []
        for obj in self._catalog.list_objects():
            if obj.orbital_period_days is None:
                continue
            age = earth_years * 365.25 / obj.orbital_period_days
            # `% 1` maps "exactly on your birthday" to 0 days, not a whole year.
            fraction_left = (1 - (age - math.floor(age))) % 1
            results.append(
                WorldAge(
                    obj=obj,
                    age=round(age, 2),
                    days_to_next_birthday=math.ceil(fraction_left * obj.orbital_period_days),
                )
            )
        return results

    # ----- Scale model -------------------------------------------------------

    def scale_model(self, sun_diameter_cm: float) -> list[ScaleItem]:
        """Shrink the Solar System until the Sun is a ball of the given size."""
        scale = sun_diameter_cm / SUN_DIAMETER_KM  # cm per km
        items: list[ScaleItem] = []
        for obj in self._catalog.list_objects():
            if obj.sun_distance_au is None and obj.slug != "sun":
                continue
            distance_m = (obj.sun_distance_au or 0) * KM_PER_AU * scale / 100
            size_cm = obj.diameter_km * scale
            items.append(
                ScaleItem(
                    obj=obj,
                    size_cm=size_cm,
                    looks_like=everyday_size(size_cm),
                    distance_m=distance_m,
                    steps=round(distance_m / STEP_M),
                )
            )
        return sorted(items, key=lambda item: item.distance_m)

    def scale_nearest_star_km(self, sun_diameter_cm: float) -> float:
        """At the same scale, how far away is Proxima Centauri (in km)?"""
        proxima = self.get_object("proxima-centauri")
        return proxima.distance_km * (sun_diameter_cm / SUN_DIAMETER_KM) / 100_000

    # ----- Travel & comparisons ---------------------------------------------

    def travel(self, obj: CelestialObject) -> list[TravelLeg]:
        if obj.distance_km == 0:
            raise ValidationError(f"You're already at {obj.name}!")
        return [
            TravelLeg(
                mode=mode,
                emoji=emoji,
                speed_kmh=speed,
                label=format_duration(obj.distance_km / speed * 3600),
            )
            for mode, emoji, speed in TRAVEL_SPEEDS_KMH
        ]

    def compare(self, a: CelestialObject, b: CelestialObject) -> SizeComparison:
        """Compare two objects' sizes the way kids picture it: 'N fit across, M fit inside'."""
        big, small = (a, b) if a.diameter_km >= b.diameter_km else (b, a)
        ratio = big.diameter_km / small.diameter_km
        volume = ratio**3
        if ratio < 1.05:
            summary = f"{a.name} and {in_sentence(b.name)} are about the same size!"
        else:
            big_name, small_name = big.name, in_sentence(small.name)
            summary = (
                f"{big_name} is about {format_number(ratio)} times wider than {small_name}. "
                f"About {format_number(round(volume))} {small.name.removeprefix('The ')}s "
                f"could fit inside {in_sentence(big_name)}!"
            )
        return SizeComparison(a=a, b=b, diameter_ratio=ratio, volume_ratio=volume, summary=summary)

    def earths_across(self, obj: CelestialObject) -> float:
        return obj.diameter_km / EARTH_DIAMETER_KM

    # ----- Cosmic address ----------------------------------------------------

    def cosmic_address(self) -> list[str]:
        """Each line of 'your address in the universe', smallest to biggest."""
        return [z.address_line for z in self._catalog.zoom_levels()]

    # ----- Tonight's sky -----------------------------------------------------

    def moon_phase(self, on: date | None = None) -> MoonPhase:
        """Approximate the Moon's phase on a date (good to about a day).

        We count days since a known new moon and take the remainder of one lunar
        cycle. Real astronomers use more precise orbital models; this simple
        version is a great first algorithm — and accurate enough to plan a night
        of Moon-watching.
        """
        on = on or self.today()
        noon = datetime(on.year, on.month, on.day, 12, tzinfo=UTC)
        days = (noon - _REFERENCE_NEW_MOON).total_seconds() / 86_400
        age = days % SYNODIC_MONTH_DAYS
        illumination = (1 - math.cos(2 * math.pi * age / SYNODIC_MONTH_DAYS)) / 2
        # Split the cycle into 8 slices centred on each named phase.
        index = int((age / SYNODIC_MONTH_DAYS) * 8 + 0.5) % 8
        name, emoji, tip = _MOON_PHASES[index]
        return MoonPhase(
            on=on,
            name=name,
            emoji=emoji,
            illumination=round(illumination, 2),
            age_days=round(age, 1),
            tip=tip,
        )

    # ----- Quiz --------------------------------------------------------------

    def quiz(self, count: int, seed: int | None = None) -> list[QuizQuestion]:
        """Pick `count` questions. A `seed` makes the pick repeatable (great for tests).

        SECURITY: `random` is NOT cryptographically secure — fine for shuffling
            quiz questions, never for tokens or passwords (use `secrets` for those).
        """
        rng = random.Random(seed)  # noqa: S311 - not security-sensitive
        questions = self._catalog.quiz_questions()
        picked = rng.sample(questions, k=min(count, len(questions)))
        # Shuffle each question's choices so the right answer isn't always first.
        return [
            QuizQuestion(
                id=q.id,
                topic=q.topic,
                prompt=q.prompt,
                choices=tuple(rng.sample(q.choices, k=len(q.choices))),
                answer=q.answer,
                explanation=q.explanation,
            )
            for q in picked
        ]

    def check_answer(self, question_id: str, choice: str) -> AnswerCheck:
        question = self._catalog.quiz_question(question_id)
        if question is None:
            raise NotFoundError(f"There's no quiz question called '{question_id}'.")
        correct = choice.strip() == question.answer
        return AnswerCheck(
            correct=correct,
            answer=question.answer,
            explanation=question.explanation,
            points=10 if correct else 0,
        )
