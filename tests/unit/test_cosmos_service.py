"""Unit tests for the Cosmic Explorer's catalog and calculations.

LESSON: Module 11 (Cosmic Explorer). See docs/11-cosmic-explorer.md

For an educational product, a wrong number is a bug that TEACHES something
false — so the maths gets the same rigour as business logic. These tests are
pure (no DB, no HTTP), which is why they're fast and easy to read.
"""

from __future__ import annotations

from datetime import date

import pytest

from pytegration.core.errors import NotFoundError, ValidationError
from pytegration.domain.cosmos import KM_PER_LIGHT_YEAR
from pytegration.repositories.cosmos_catalog import CosmosCatalog
from pytegration.services.cosmos_service import (
    CosmosService,
    everyday_size,
    format_distance,
    format_duration,
    format_number,
)


@pytest.fixture
def cosmos() -> CosmosService:
    # Pin "today" so date-dependent messages ("around the year 2022") are stable.
    return CosmosService(CosmosCatalog(), today=date(2026, 11, 22))


# ----- Data integrity: the atlas itself must be self-consistent ------------------


def test_catalog_slugs_and_names_are_unique() -> None:
    catalog = CosmosCatalog()
    slugs = [o.slug for o in catalog.list_objects()]
    assert len(slugs) == len(set(slugs))
    # Every alias resolves to exactly one object (no alias silently shadows another).
    all_names = [n for o in catalog.list_objects() for n in set(o.names)]
    assert len(all_names) == len(set(all_names)), "two objects share a name/alias"


def test_every_quiz_answer_is_one_of_its_choices() -> None:
    for q in CosmosCatalog().quiz_questions():
        assert q.answer in q.choices, q.id
        assert len(set(q.choices)) == len(q.choices), q.id


def test_zoom_levels_get_strictly_bigger() -> None:
    levels = CosmosCatalog().zoom_levels()
    sizes = [z.size_km for z in levels]
    assert sizes == sorted(sizes) and len(set(sizes)) == len(sizes)
    assert [z.order for z in levels] == list(range(1, len(levels) + 1))


def test_other_planets_fit_between_earth_and_moon(cosmos: CosmosService) -> None:
    """Verifies a claim the zoom page makes, using the catalog's own numbers."""
    planets = [
        o for o in cosmos.catalog.list_objects() if o.kind.value == "planet" and o.slug != "earth"
    ]
    assert len(planets) == 7
    assert sum(p.diameter_km for p in planets) < cosmos.get_object("moon").distance_km


# ----- Lookups -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "slug"),
    [("Mars", "mars"), ("the Moon", "moon"), ("NORTH STAR", "polaris"), ("m31", "andromeda")],
)
def test_find_by_name_or_alias(cosmos: CosmosService, query: str, slug: str) -> None:
    assert cosmos.get_object(query).slug == slug


def test_unknown_object_raises_helpful_error(cosmos: CosmosService) -> None:
    with pytest.raises(NotFoundError, match="Try one of"):
        cosmos.get_object("Tatooine")


def test_find_mentions_respects_word_boundaries_and_order() -> None:
    found = CosmosCatalog().find_mentions("On Sunday: is the Moon bigger than Jupiter or the Sun?")
    assert [o.slug for o in found] == ["moon", "jupiter", "sun"]  # not "sun" from "Sunday"


# ----- Formatting ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(149_600_000, "149.6 million"), (1_000_000, "1 million"), (1321, "1,321"), (2.5, "2.5")],
)
def test_format_number(value: float, expected: str) -> None:
    assert format_number(value) == expected


def test_format_distance_switches_to_light_years() -> None:
    assert format_distance(0.109) == "109 m"
    assert format_distance(384_400) == "384,400 km"
    assert format_distance(4.246 * KM_PER_LIGHT_YEAR) == "4.2 light-years"
    assert format_distance(KM_PER_LIGHT_YEAR) == "1 light-year"


def test_format_duration() -> None:
    assert format_duration(1.28) == "1.3 seconds"
    assert format_duration(499) == "8 minutes 19 seconds"
    assert format_duration(3 * 86_400) == "3 days"


def test_everyday_size() -> None:
    assert everyday_size(0.27) == "a peppercorn"  # Earth when the Sun is a 30 cm ball
    assert everyday_size(30) == "a beach ball"


# ----- Light Time Machine -----------------------------------------------------------


def test_sunlight_is_about_eight_minutes_old(cosmos: CosmosService) -> None:
    light = cosmos.light_travel_for(cosmos.get_object("sun"))
    assert light.label.startswith("8 minutes")
    assert light.message == "You see the Sun as it was 8 minutes 19 seconds ago."


def test_nearby_star_light_reports_a_calendar_year(cosmos: CosmosService) -> None:
    light = cosmos.light_travel_for(cosmos.get_object("proxima-centauri"))
    assert light.left_in_year == 2022
    assert "2022" in light.message


def test_andromeda_light_predates_modern_humans(cosmos: CosmosService) -> None:
    light = cosmos.light_travel_for(cosmos.get_object("andromeda"))
    assert light.label == "2.5 million years"
    assert light.before_event == "the first modern humans lived in Africa"


def test_time_machine_bounds(cosmos: CosmosService) -> None:
    assert "before the Sun was born" in cosmos.time_machine(13_000_000_000).message
    with pytest.raises(ValidationError):
        cosmos.time_machine(20_000_000_000)


# ----- Space Gym ------------------------------------------------------------------


def test_weight_and_jump_on_the_moon(cosmos: CosmosService) -> None:
    result = cosmos.weight_on(cosmos.get_object("moon"), 30)
    assert result.weight == pytest.approx(30 * 0.165, abs=0.05)
    assert result.jump_height_m == pytest.approx(0.3 / 0.165, abs=0.01)


def test_cannot_stand_on_a_galaxy(cosmos: CosmosService) -> None:
    with pytest.raises(ValidationError, match="no surface"):
        cosmos.weight_on(cosmos.get_object("andromeda"), 30)


def test_ages(cosmos: CosmosService) -> None:
    ages = {a.obj.slug: a for a in cosmos.ages(10)}
    assert ages["mercury"].age == pytest.approx(41.5, abs=0.1)
    assert ages["earth"].age == 10
    assert ages["earth"].days_to_next_birthday == 0  # exactly 10 = birthday today


# ----- Scale model, travel, compare --------------------------------------------------


def test_scale_model_matches_the_classic_beach_ball_walk(cosmos: CosmosService) -> None:
    items = {i.obj.slug: i for i in cosmos.scale_model(30)}
    assert items["sun"].distance_m == 0
    assert items["earth"].distance_m == pytest.approx(32, abs=1)
    assert items["earth"].looks_like == "a peppercorn"
    assert items["neptune"].distance_m == pytest.approx(969, abs=5)
    assert cosmos.scale_nearest_star_km(30) == pytest.approx(8_650, rel=0.01)


def test_drive_to_the_moon_takes_about_160_days(cosmos: CosmosService) -> None:
    legs = {leg.mode: leg for leg in cosmos.travel(cosmos.get_object("moon"))}
    assert legs["car on a highway"].label == "160 days"
    assert legs["light"].label == "1.3 seconds"


def test_compare_jupiter_and_earth(cosmos: CosmosService) -> None:
    result = cosmos.compare(cosmos.get_object("earth"), cosmos.get_object("jupiter"))
    assert result.diameter_ratio == pytest.approx(11, abs=0.1)
    assert "1,321 Earths could fit inside Jupiter" in result.summary


# ----- Moon phase ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("on", "expected"),
    [
        (date(2024, 4, 8), "New Moon"),  # the day of the 2024 North American eclipse
        (date(2024, 4, 23), "Full Moon"),
        (date(2025, 1, 6), "First Quarter"),
    ],
)
def test_moon_phase_on_known_dates(cosmos: CosmosService, on: date, expected: str) -> None:
    assert cosmos.moon_phase(on).name == expected


# ----- Quiz ---------------------------------------------------------------------


def test_quiz_is_repeatable_with_a_seed(cosmos: CosmosService) -> None:
    first = [(q.id, q.choices) for q in cosmos.quiz(5, seed=42)]
    second = [(q.id, q.choices) for q in cosmos.quiz(5, seed=42)]
    assert first == second
    assert len({qid for qid, _ in first}) == 5


def test_check_answer(cosmos: CosmosService) -> None:
    assert cosmos.check_answer("biggest-planet", "Jupiter").correct
    wrong = cosmos.check_answer("biggest-planet", "Saturn")
    assert not wrong.correct and wrong.answer == "Jupiter" and wrong.points == 0
    with pytest.raises(NotFoundError):
        cosmos.check_answer("nope", "x")
