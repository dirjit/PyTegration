"""Behavioral evals for the agent.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md

WHAT IS AN "EVAL"?
    A test of BEHAVIOR rather than implementation: given an input, did the agent
    take the right ACTIONS and reach the right OUTCOME? Evals are how you guard an
    agent against regressions as prompts, tools, or models change. Here they run
    against the deterministic MockProvider so they are stable in CI.
    PRODUCTION UPGRADE: run a parallel suite against the real model on a schedule
    and assert on outcomes (e.g. "a task was created") rather than exact wording,
    since real model output varies.

Each case states a user message and the tool(s) we expect the agent to use.
"""

from __future__ import annotations

import pytest

from pytegration.agent.loop import run_agent
from pytegration.agent.mock_provider import MockProvider
from pytegration.agent.prompts import SYSTEM_PROMPT
from pytegration.agent.tools import task_toolbox
from pytegration.services.task_service import TaskService

# SYNTAX TIP: `@pytest.mark.parametrize` runs the SAME test body once per row —
#   the idiomatic, low-boilerplate way to write table-driven tests (Java devs:
#   think JUnit 5 `@ParameterizedTest` with a `@MethodSource`).
EVAL_CASES = [
    ("create a task to write docs", {"create_task"}),
    ("show me my tasks", {"list_tasks"}),
    ("how many open tasks do I have?", {"summarize_tasks"}),
    ("add a low priority task to refactor, then summarize", {"create_task", "summarize_tasks"}),
]


@pytest.mark.parametrize(("message", "expected_tools"), EVAL_CASES)
async def test_agent_uses_expected_tools(
    task_service: TaskService, message: str, expected_tools: set[str]
) -> None:
    """The agent should call (at least) the tools each request implies."""
    result = await run_agent(
        provider=MockProvider(),
        toolbox=task_toolbox(task_service),
        user_message=message,
        system_prompt=SYSTEM_PROMPT,
        max_iterations=6,
    )

    used = {step.tool for step in result.trace}
    assert expected_tools <= used, f"{message!r} used {used}, expected ⊇ {expected_tools}"
    assert result.reply  # always ends with a natural-language answer


async def test_agent_stops_at_iteration_cap(task_service: TaskService) -> None:
    """A pathological provider that never finishes is stopped by the cap.

    WHY test this? The iteration cap is a critical safety guardrail. We prove it
        actually halts a runaway loop instead of spinning forever.
    """
    from pytegration.agent.provider import AssistantTurn, ConversationItem, ToolCall, ToolSpec
    from pytegration.core.errors import AgentError

    class _NeverStops:
        """A provider that always asks for another tool call."""

        async def generate(
            self, *, system: str, conversation: list[ConversationItem], tools: list[ToolSpec]
        ) -> AssistantTurn:
            return AssistantTurn(
                text="", tool_calls=[ToolCall(id="x", name="summarize_tasks", arguments={})]
            )

    with pytest.raises(AgentError, match="did not finish"):
        await run_agent(
            provider=_NeverStops(),
            toolbox=task_toolbox(task_service),
            user_message="loop forever",
            system_prompt=SYSTEM_PROMPT,
            max_iterations=3,
        )


# ----- Nova, the kids' Space Guide (v0.2) ------------------------------------------
# Evals for an educational agent check two things: it picks the GROUNDING tool for
# the question (so numbers come from tested code), and its reply carries that fact.
GUIDE_CASES = [
    ("How much would I weigh on the Moon?", "weight_on_world", "Moon"),
    ("Is Jupiter bigger than Earth?", "compare_sizes", "11 times wider"),
    ("How long ago did Betelgeuse's light leave?", "light_time_machine", "550 years"),
    ("How long would it take to fly to Mars?", "travel_time", "Mars"),
    ("What is my cosmic address?", "cosmic_address", "Milky Way"),
    ("Tell me about Pluto", "lookup_object", "dwarf planet"),
]


@pytest.mark.parametrize(("message", "expected_tool", "expected_text"), GUIDE_CASES)
async def test_guide_uses_grounding_tools(
    message: str, expected_tool: str, expected_text: str
) -> None:
    from pytegration.agent.guide_tools import guide_toolbox
    from pytegration.agent.prompts import GUIDE_SYSTEM_PROMPT
    from pytegration.repositories.cosmos_catalog import CosmosCatalog
    from pytegration.services.cosmos_service import CosmosService

    result = await run_agent(
        provider=MockProvider(),
        toolbox=guide_toolbox(CosmosService(CosmosCatalog())),
        user_message=message,
        system_prompt=GUIDE_SYSTEM_PROMPT,
        max_iterations=6,
    )
    assert [step.tool for step in result.trace] == [expected_tool]
    assert all(step.ok for step in result.trace)
    assert expected_text in result.reply


async def test_guide_without_a_space_topic_offers_ideas() -> None:
    from pytegration.agent.guide_tools import guide_toolbox
    from pytegration.agent.prompts import GUIDE_SYSTEM_PROMPT
    from pytegration.repositories.cosmos_catalog import CosmosCatalog
    from pytegration.services.cosmos_service import CosmosService

    result = await run_agent(
        provider=MockProvider(),
        toolbox=guide_toolbox(CosmosService(CosmosCatalog())),
        user_message="hello!",
        system_prompt=GUIDE_SYSTEM_PROMPT,
        max_iterations=6,
    )
    assert result.trace == []
    assert "Nova" in result.reply
