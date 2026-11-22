"""Cosmic Explorer endpoints — the public, read-only atlas of the universe.

LESSON: Module 11 (Cosmic Explorer). See docs/11-cosmic-explorer.md
LAYER:  api

SECURITY — why are these routes PUBLIC (no API key)?
    They expose only curated, read-only reference data and pure calculations:
    no user data, no writes, no LLM cost. A kid opening the explorer page should
    not need a password. They still pass through the per-IP rate limiter and
    strict input validation (every query parameter below has bounds). The Space
    Guide (an LLM endpoint with real cost) stays behind the API key — see
    api/routes/agent.py. Decide "public or protected" per route by asking:
    what's the worst a stranger could do with it?

PRIVACY: nothing here accepts or stores personal data. The explorer page lets a
    kid type their name onto their "cosmic address" card, but that never leaves
    the browser.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query

from pytegration.api.deps import CosmosServiceDep as CosmosDep
from pytegration.domain.cosmos import SPEED_OF_LIGHT_KM_S, CelestialObject, ObjectKind, ZoomLevel
from pytegration.domain.cosmos import Career as CareerEntity
from pytegration.schemas.cosmos import (
    AgeOut,
    AtlasOut,
    CareerOut,
    CelestialObjectOut,
    CompareOut,
    LightTravelOut,
    MoonPhaseOut,
    QuizAnswerIn,
    QuizAnswerOut,
    QuizQuestionOut,
    ScaleItemOut,
    ScaleModelOut,
    TravelLegOut,
    TravelOut,
    WeightOut,
    ZoomLevelOut,
)
from pytegration.services.cosmos_service import (
    CosmosService,
    LightTravel,
    format_distance,
    format_duration,
    format_number,
)

router = APIRouter(prefix="/cosmos", tags=["cosmos"])

# Path/query bounds shared by every "name an object" parameter.
# SECURITY: bounding free-text input length is cheap insurance against abuse.
ObjectName = Annotated[str, Path(min_length=1, max_length=60)]


# =============================================================================
# Mappers: domain records -> API DTOs.
# =============================================================================


def _light_out(light: LightTravel) -> LightTravelOut:
    return LightTravelOut(
        seconds=light.seconds,
        label=light.label,
        left_in_year=light.left_in_year,
        before_event=light.before_event,
        message=light.message,
    )


def _object_out(service: CosmosService, obj: CelestialObject) -> CelestialObjectOut:
    return CelestialObjectOut(
        slug=obj.slug,
        name=obj.name,
        kind=obj.kind,
        emoji=obj.emoji,
        color=obj.color,
        tagline=obj.tagline,
        fun_facts=list(obj.fun_facts),
        distance_km=obj.distance_km,
        distance_label=format_distance(obj.distance_km) if obj.distance_km else "You are here!",
        distance_varies=obj.distance_varies,
        diameter_km=obj.diameter_km,
        diameter_label=format_distance(obj.diameter_km),
        earths_across=round(service.earths_across(obj), 4),
        surface_gravity_g=obj.surface_gravity_g,
        orbital_period_days=obj.orbital_period_days,
        day_length_hours=obj.day_length_hours,
        moons=obj.moons,
        light=_light_out(service.light_travel_for(obj)),
    )


def _zoom_out(level: ZoomLevel) -> ZoomLevelOut:
    return ZoomLevelOut(
        order=level.order,
        slug=level.slug,
        title=level.title,
        address_line=level.address_line,
        emoji=level.emoji,
        color=level.color,
        size_km=level.size_km,
        size_label=format_distance(level.size_km),
        light_crossing=format_duration(level.size_km / SPEED_OF_LIGHT_KM_S),
        contains=level.contains,
        analogy=level.analogy,
        fun_fact=level.fun_fact,
    )


def _career_out(career: CareerEntity) -> CareerOut:
    return CareerOut(
        slug=career.slug,
        title=career.title,
        emoji=career.emoji,
        what_they_do=career.what_they_do,
        helpful_subjects=list(career.helpful_subjects),
        try_this=career.try_this,
    )


# =============================================================================
# Routes
# =============================================================================


@router.get("/atlas", response_model=AtlasOut, summary="Everything the explorer page needs")
async def atlas(service: CosmosDep) -> AtlasOut:
    """One request for the whole atlas: zoom levels, objects and careers.

    WHY a bundle endpoint? The page would otherwise make several calls on load.
        Fewer round trips = faster on slow school Wi-Fi, and fewer rate-limit
        tokens spent. A classic "backend for frontend" (BFF) trade-off.
    """
    catalog = service.catalog
    return AtlasOut(
        zoom_levels=[_zoom_out(z) for z in catalog.zoom_levels()],
        objects=[_object_out(service, o) for o in catalog.list_objects()],
        careers=[_career_out(c) for c in catalog.careers()],
    )


@router.get("/zoom", response_model=list[ZoomLevelOut], summary="The Cosmic Zoom levels")
async def zoom_levels(service: CosmosDep) -> list[ZoomLevelOut]:
    return [_zoom_out(z) for z in service.catalog.zoom_levels()]


@router.get("/address", response_model=list[str], summary="Your address in the universe")
async def cosmic_address(service: CosmosDep) -> list[str]:
    return service.cosmic_address()


@router.get("/objects", response_model=list[CelestialObjectOut], summary="List objects")
async def list_objects(
    service: CosmosDep, kind: ObjectKind | None = None
) -> list[CelestialObjectOut]:
    return [_object_out(service, o) for o in service.catalog.list_objects(kind)]


@router.get("/objects/{name}", response_model=CelestialObjectOut, summary="Look up one object")
async def get_object(service: CosmosDep, name: ObjectName) -> CelestialObjectOut:
    return _object_out(service, service.get_object(name))


@router.get("/time-machine", response_model=LightTravelOut, summary="How old is starlight?")
async def time_machine(
    service: CosmosDep,
    light_years: Annotated[float, Query(gt=0, le=13_800_000_000)],
) -> LightTravelOut:
    return _light_out(service.time_machine(light_years))


@router.get("/weight", response_model=list[WeightOut], summary="Your weight on other worlds")
async def weight(
    service: CosmosDep,
    earth_weight: Annotated[float, Query(gt=0, le=500, description="kg or lb — same unit back")],
) -> list[WeightOut]:
    return [
        WeightOut(
            slug=w.obj.slug,
            name=w.obj.name,
            emoji=w.obj.emoji,
            gravity_g=w.obj.surface_gravity_g or 0,
            weight=w.weight,
            jump_height_m=w.jump_height_m,
        )
        for w in service.weights(earth_weight)
    ]


@router.get("/age", response_model=list[AgeOut], summary="Your age on other worlds")
async def age(
    service: CosmosDep, earth_years: Annotated[float, Query(gt=0, le=130)]
) -> list[AgeOut]:
    return [
        AgeOut(
            slug=a.obj.slug,
            name=a.obj.name,
            emoji=a.obj.emoji,
            age=a.age,
            days_to_next_birthday=a.days_to_next_birthday,
        )
        for a in service.ages(earth_years)
    ]


@router.get("/scale-model", response_model=ScaleModelOut, summary="Shrink the Solar System")
async def scale_model(
    service: CosmosDep,
    sun_diameter_cm: Annotated[float, Query(ge=1, le=500)] = 30,
) -> ScaleModelOut:
    items = service.scale_model(sun_diameter_cm)
    star_km = service.scale_nearest_star_km(sun_diameter_cm)
    return ScaleModelOut(
        sun_diameter_cm=sun_diameter_cm,
        items=[
            ScaleItemOut(
                slug=i.obj.slug,
                name=i.obj.name,
                emoji=i.obj.emoji,
                color=i.obj.color,
                size_cm=round(i.size_cm, 4),
                looks_like=i.looks_like,
                distance_m=round(i.distance_m, 1),
                steps=i.steps,
            )
            for i in items
        ],
        nearest_star_km=round(star_km),
        nearest_star_message=(
            f"At this scale the nearest star, Proxima Centauri, would be about "
            f"{format_number(star_km)} km away — space is mostly empty!"
        ),
    )


@router.get("/travel/{name}", response_model=TravelOut, summary="How long to get there?")
async def travel(service: CosmosDep, name: ObjectName) -> TravelOut:
    obj = service.get_object(name)
    return TravelOut(
        destination=obj.name,
        distance_label=format_distance(obj.distance_km),
        legs=[
            TravelLegOut(mode=t.mode, emoji=t.emoji, speed_kmh=t.speed_kmh, label=t.label)
            for t in service.travel(obj)
        ],
    )


@router.get("/compare", response_model=CompareOut, summary="Which is bigger?")
async def compare(
    service: CosmosDep,
    a: Annotated[str, Query(min_length=1, max_length=60)],
    b: Annotated[str, Query(min_length=1, max_length=60)],
) -> CompareOut:
    result = service.compare(service.get_object(a), service.get_object(b))
    return CompareOut(
        a=result.a.name,
        b=result.b.name,
        diameter_ratio=round(result.diameter_ratio, 3),
        volume_ratio=round(result.volume_ratio, 3),
        summary=result.summary,
    )


@router.get("/moon", response_model=MoonPhaseOut, summary="Tonight's Moon phase")
async def moon(service: CosmosDep, on: date | None = None) -> MoonPhaseOut:
    phase = service.moon_phase(on)
    return MoonPhaseOut(
        date=phase.on,
        name=phase.name,
        emoji=phase.emoji,
        illumination=phase.illumination,
        age_days=phase.age_days,
        tip=phase.tip,
    )


@router.get("/quiz", response_model=list[QuizQuestionOut], summary="Get quiz questions")
async def quiz(
    service: CosmosDep,
    count: Annotated[int, Query(ge=1, le=20)] = 5,
    seed: Annotated[int | None, Query(ge=0, le=2**31)] = None,
) -> list[QuizQuestionOut]:
    return [
        QuizQuestionOut(id=q.id, topic=q.topic, prompt=q.prompt, choices=list(q.choices))
        for q in service.quiz(count, seed)
    ]


@router.post("/quiz/answer", response_model=QuizAnswerOut, summary="Check a quiz answer")
async def quiz_answer(service: CosmosDep, payload: QuizAnswerIn) -> QuizAnswerOut:
    result = service.check_answer(payload.question_id, payload.choice)
    return QuizAnswerOut(
        correct=result.correct,
        answer=result.answer,
        explanation=result.explanation,
        points=result.points,
    )


@router.get("/careers", response_model=list[CareerOut], summary="Jobs in space science")
async def careers(service: CosmosDep) -> list[CareerOut]:
    return [_career_out(c) for c in service.catalog.careers()]
