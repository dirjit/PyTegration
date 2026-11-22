"""Space Guide tools — what "Nova", the kids' space guide, is allowed to do.

LESSON: Module 11 (Cosmic Explorer). See docs/11-cosmic-explorer.md
LAYER:  agent

WHY give a chatbot tools for facts it might already "know"?
    LLMs can misremember numbers. For an educational product aimed at children,
    a confidently wrong fact is a real harm. So every number Nova says comes from
    a tool that reads our reviewed atlas and runs our tested maths — the model's
    job is to choose the right tool and explain the result kindly, not to recall
    figures from memory. This is "grounding", and it is the single most useful
    pattern for trustworthy LLM features.

SECURITY: every tool is READ-ONLY. There is nothing Nova can change, so even a
    successful prompt injection has no dangerous action to take. Arguments are
    bounded and validated exactly like the task tools.

Each handler returns a `summary` sentence the model can paraphrase (and the
offline mock repeats verbatim), alongside the raw numbers.
"""

from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from pytegration.agent.toolbox import Tool, Toolbox
from pytegration.services.cosmos_service import (
    CosmosService,
    format_distance,
    format_number,
    in_sentence,
)

_Name = Field(min_length=1, max_length=60, description="Name of a planet, star, galaxy, etc.")


class _NameArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = _Name


class _WeightArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = _Name
    earth_weight: float = Field(gt=0, le=500, description="Weight on Earth.")
    unit: Literal["kg", "lb"] = Field(default="kg", description="Unit of earth_weight.")


class _CompareArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: str = _Name
    b: str = _Name


class _NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def _lookup(cosmos: CosmosService, args: BaseModel) -> dict[str, Any]:
    obj = cosmos.get_object(cast(_NameArgs, args).name)
    distance = format_distance(obj.distance_km) if obj.distance_km else "right here"
    return {
        "name": obj.name,
        "kind": obj.kind.value,
        "tagline": obj.tagline,
        "distance": distance,
        "diameter": format_distance(obj.diameter_km),
        "fun_facts": list(obj.fun_facts),
        "summary": f"{obj.emoji} {obj.name}: {obj.tagline} Fun fact: {obj.fun_facts[0]}",
    }


async def _light(cosmos: CosmosService, args: BaseModel) -> dict[str, Any]:
    obj = cosmos.get_object(cast(_NameArgs, args).name)
    light = cosmos.light_travel_for(obj)
    return {"name": obj.name, "light_travel": light.label, "summary": light.message}


async def _weight(cosmos: CosmosService, args: BaseModel) -> dict[str, Any]:
    weight_args = cast(_WeightArgs, args)
    obj = cosmos.get_object(weight_args.name)
    result = cosmos.weight_on(obj, weight_args.earth_weight)
    return {
        "name": obj.name,
        "weight": result.weight,
        "jump_height_m": result.jump_height_m,
        "summary": (
            f"If you weigh {format_number(weight_args.earth_weight)} {weight_args.unit} on Earth, "
            f"you'd weigh about {format_number(result.weight)} {weight_args.unit} on "
            f"{in_sentence(obj.name)} — and could jump about "
            f"{format_number(result.jump_height_m)} m high!"
        ),
    }


async def _compare(cosmos: CosmosService, args: BaseModel) -> dict[str, Any]:
    compare_args = cast(_CompareArgs, args)
    result = cosmos.compare(cosmos.get_object(compare_args.a), cosmos.get_object(compare_args.b))
    return {"diameter_ratio": round(result.diameter_ratio, 2), "summary": result.summary}


async def _travel(cosmos: CosmosService, args: BaseModel) -> dict[str, Any]:
    obj = cosmos.get_object(cast(_NameArgs, args).name)
    legs = cosmos.travel(obj)
    by_mode = {leg.mode: leg.label for leg in legs}
    car, rocket = legs[1], legs[3]
    return {
        "name": obj.name,
        "times": by_mode,
        "summary": (
            f"Getting to {in_sentence(obj.name)} would take about {car.label} by car "
            f"and {rocket.label} on the fastest spacecraft ever built."
        ),
    }


async def _address(cosmos: CosmosService, args: BaseModel) -> dict[str, Any]:
    lines = cosmos.cosmic_address()
    return {"address": lines, "summary": "Your cosmic address: " + " → ".join(lines) + "."}


# THE ALLOW-LIST for Nova. Read-only by construction.
GUIDE_TOOLS: dict[str, Tool[CosmosService]] = {
    "lookup_object": Tool(
        name="lookup_object",
        description="Get kid-friendly facts about a planet, moon, star, galaxy, nebula or spacecraft.",
        args_model=_NameArgs,
        handler=_lookup,
    ),
    "light_time_machine": Tool(
        name="light_time_machine",
        description="How long light from an object takes to reach Earth, and what was happening on Earth when it set off.",
        args_model=_NameArgs,
        handler=_light,
    ),
    "weight_on_world": Tool(
        name="weight_on_world",
        description="What someone would weigh (and how high they could jump) on another world.",
        args_model=_WeightArgs,
        handler=_weight,
    ),
    "compare_sizes": Tool(
        name="compare_sizes",
        description="Compare the sizes of two objects (how many fit across / inside).",
        args_model=_CompareArgs,
        handler=_compare,
    ),
    "travel_time": Tool(
        name="travel_time",
        description="How long it would take to travel to an object by car, plane, fastest spacecraft, or light.",
        args_model=_NameArgs,
        handler=_travel,
    ),
    "cosmic_address": Tool(
        name="cosmic_address",
        description="Our full address in the universe, from Earth out to the observable universe.",
        args_model=_NoArgs,
        handler=_address,
    ),
}


def guide_toolbox(cosmos: CosmosService) -> Toolbox[CosmosService]:
    """Nova's toolbox, bound to a CosmosService."""
    return Toolbox(cosmos, GUIDE_TOOLS)
