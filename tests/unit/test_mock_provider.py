"""Unit tests for the deterministic MockProvider.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
"""

from __future__ import annotations

from pytegration.agent.mock_provider import MockProvider
from pytegration.agent.provider import (
    AssistantMessage,
    ConversationItem,
    ToolResult,
    ToolResultsMessage,
    UserMessage,
)

provider = MockProvider()


async def test_create_intent_emits_create_tool_call() -> None:
    """A 'create' request first asks to run the create_task tool."""
    convo: list[ConversationItem] = [UserMessage(text="Please create a deploy task")]
    turn = await provider.generate(system="", conversation=convo, tools=[])

    assert turn.tool_calls
    assert turn.tool_calls[0].name == "create_task"
    assert turn.tool_calls[0].arguments["title"]  # a non-empty title was extracted


async def test_high_priority_keyword_is_detected() -> None:
    """The word 'high' maps to a high-priority create call."""
    convo: list[ConversationItem] = [UserMessage(text="add a high priority task to deploy")]
    turn = await provider.generate(system="", conversation=convo, tools=[])
    assert turn.tool_calls[0].arguments["priority"] == "high"


async def test_multi_step_then_final_answer() -> None:
    """Create + summarize stepping: tool, tool, then a final text reply.

    We simulate the loop by appending the assistant turn and a tool result, then
    asking the provider for the next turn — mirroring agent/loop.py.
    """
    convo: list[ConversationItem] = [
        UserMessage(text="create a deploy task then summarize my open tasks")
    ]

    # Step 1: expect a create_task call.
    t1 = await provider.generate(system="", conversation=convo, tools=[])
    assert t1.tool_calls[0].name == "create_task"
    convo.append(AssistantMessage(text="", tool_calls=t1.tool_calls))
    convo.append(ToolResultsMessage(results=[ToolResult(call_id="mock-0", content="{}")]))

    # Step 2: expect a summarize_tasks call.
    t2 = await provider.generate(system="", conversation=convo, tools=[])
    assert t2.tool_calls[0].name == "summarize_tasks"
    convo.append(AssistantMessage(text="", tool_calls=t2.tool_calls))
    convo.append(
        ToolResultsMessage(
            results=[ToolResult(call_id="mock-1", content='{"total": 1, "open": 1}')]
        )
    )

    # Step 3: no more tools — a final natural-language answer derived from results.
    t3 = await provider.generate(system="", conversation=convo, tools=[])
    assert not t3.tool_calls
    assert "1" in t3.text  # mentions the counts from the summary
