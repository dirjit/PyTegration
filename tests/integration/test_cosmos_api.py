"""Integration tests for the public Cosmic Explorer API and web page.

LESSON: Module 11 (Cosmic Explorer). See docs/11-cosmic-explorer.md
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from pytegration.api.deps import get_cosmos_service
from pytegration.core.config import Settings
from pytegration.main import create_app
from pytegration.repositories.cosmos_catalog import CosmosCatalog
from pytegration.services.cosmos_service import CosmosService

COSMOS = "/api/v1/cosmos"


@pytest_asyncio.fixture
async def public_client(settings: Settings) -> AsyncIterator[AsyncClient]:
    """A client with NO API key — exactly what a kid's browser looks like.

    It also pins "today" via a dependency override, so date-based answers are
    stable. JAVA NOTE: like `@MockBean`-replacing a clock in a Spring test.
    """
    app = create_app(settings=settings)
    app.dependency_overrides[get_cosmos_service] = lambda: CosmosService(
        CosmosCatalog(), today=date(2026, 11, 22)
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_cosmos_api_is_public(public_client: AsyncClient) -> None:
    """SECURITY decision under test: the read-only atlas needs no API key..."""
    response = await public_client.get(f"{COSMOS}/atlas")
    assert response.status_code == 200
    body = response.json()
    assert len(body["zoom_levels"]) == 8
    assert {o["slug"] for o in body["objects"]} >= {"earth", "moon", "sun", "andromeda"}
    assert body["careers"]


async def test_protected_routes_stay_protected(public_client: AsyncClient) -> None:
    """...while adding a public router did NOT open up the protected ones."""
    assert (await public_client.get("/api/v1/tasks")).status_code == 401
    assert (
        await public_client.post("/api/v1/agent/guide", json={"message": "hi"})
    ).status_code == 401


async def test_object_lookup_by_alias(public_client: AsyncClient) -> None:
    body = (await public_client.get(f"{COSMOS}/objects/north star")).json()
    assert body["slug"] == "polaris"
    assert body["light"]["before_event"]


async def test_unknown_object_is_404_with_envelope(public_client: AsyncClient) -> None:
    response = await public_client.get(f"{COSMOS}/objects/tatooine")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_filter_objects_by_kind(public_client: AsyncClient) -> None:
    body = (await public_client.get(f"{COSMOS}/objects", params={"kind": "planet"})).json()
    assert len(body) == 8


@pytest.mark.parametrize("weight", [0, -5, 501])
async def test_weight_input_is_bounded(public_client: AsyncClient, weight: float) -> None:
    response = await public_client.get(f"{COSMOS}/weight", params={"earth_weight": weight})
    assert response.status_code == 422


async def test_weight_on_worlds(public_client: AsyncClient) -> None:
    rows = (await public_client.get(f"{COSMOS}/weight", params={"earth_weight": 30})).json()
    by_slug = {r["slug"]: r for r in rows}
    assert by_slug["earth"]["weight"] == 30
    assert by_slug["moon"]["weight"] < by_slug["mars"]["weight"] < by_slug["earth"]["weight"]
    assert "andromeda" not in by_slug  # nothing to stand on


async def test_time_machine(public_client: AsyncClient) -> None:
    body = (
        await public_client.get(f"{COSMOS}/time-machine", params={"light_years": 26_700})
    ).json()
    assert "before people began farming" in body["message"]


async def test_scale_model_and_compare_and_travel(public_client: AsyncClient) -> None:
    model = (await public_client.get(f"{COSMOS}/scale-model")).json()
    assert model["items"][0]["slug"] == "sun"
    assert "Proxima Centauri" in model["nearest_star_message"]

    compare = (
        await public_client.get(f"{COSMOS}/compare", params={"a": "sun", "b": "earth"})
    ).json()
    assert "1.3 million Earths" in compare["summary"]

    travel = (await public_client.get(f"{COSMOS}/travel/moon")).json()
    assert [leg["mode"] for leg in travel["legs"]][-1] == "light"


async def test_travel_to_earth_is_a_friendly_422(public_client: AsyncClient) -> None:
    response = await public_client.get(f"{COSMOS}/travel/earth")
    assert response.status_code == 422
    assert "already" in response.json()["error"]["message"]


async def test_moon_phase_uses_injected_clock(public_client: AsyncClient) -> None:
    today = (await public_client.get(f"{COSMOS}/moon")).json()
    assert today["date"] == "2026-11-22"
    on = (await public_client.get(f"{COSMOS}/moon", params={"on": "2024-04-23"})).json()
    assert on["name"] == "Full Moon"


async def test_quiz_does_not_leak_answers(public_client: AsyncClient) -> None:
    """SECURITY: the answer is checked server-side and never sent with the question."""
    questions = (await public_client.get(f"{COSMOS}/quiz", params={"count": 3, "seed": 7})).json()
    assert len(questions) == 3
    for q in questions:
        assert "answer" not in q and "explanation" not in q


async def test_quiz_answer_roundtrip(public_client: AsyncClient) -> None:
    right = await public_client.post(
        f"{COSMOS}/quiz/answer", json={"question_id": "sun-is", "choice": "A star"}
    )
    assert right.json()["correct"] is True and right.json()["points"] == 10
    wrong = await public_client.post(
        f"{COSMOS}/quiz/answer", json={"question_id": "sun-is", "choice": "A planet"}
    )
    assert wrong.json()["correct"] is False
    extra = await public_client.post(
        f"{COSMOS}/quiz/answer", json={"question_id": "sun-is", "choice": "x", "hack": 1}
    )
    assert extra.status_code == 422


async def test_explorer_page_is_served_with_security_headers(public_client: AsyncClient) -> None:
    page = await public_client.get("/explore/")
    assert page.status_code == 200
    assert "Cosmic Explorer" in page.text
    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["x-content-type-options"] == "nosniff"
    assert (await public_client.get("/explore/app.js")).status_code == 200


async def test_root_redirects_to_explorer(public_client: AsyncClient) -> None:
    response = await public_client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/explore/"


async def test_static_assets_do_not_spend_rate_limit(settings: Settings) -> None:
    """Loading the page's files must not use up a kid's API request budget."""
    tight = settings.model_copy(update={"rate_limit_capacity": 2})
    app = create_app(settings=tight)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for _ in range(5):
            assert (await client.get("/explore/styles.css")).status_code == 200
        assert (await client.get(f"{COSMOS}/zoom")).status_code == 200
        assert (await client.get(f"{COSMOS}/zoom")).status_code == 200
        assert (await client.get(f"{COSMOS}/zoom")).status_code == 429
