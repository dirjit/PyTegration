"""The agent loop — the heart of the agentic layer.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
LAYER:  agent

THE LOOP, IN ONE PARAGRAPH:
    Send the conversation + tools to the model. If it returns a final answer,
    we're done. If it returns tool calls, execute each (safely, via tools.py),
    append the results to the conversation, and loop again — until the model
    answers or we hit a hard iteration cap. That cap is the critical guardrail
    against runaway loops and runaway cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from pytegration.agent.provider import (
    AssistantMessage,
    ConversationItem,
    LLMProvider,
    ToolResultsMessage,
    UserMessage,
)
from pytegration.agent.tools import dispatch_tool_call, tool_specs
from pytegration.core.errors import AgentError
from pytegration.core.logging import get_logger
from pytegration.services.task_service import TaskService

logger = get_logger(__name__)


@dataclass(frozen=True)
class ToolCallTrace:
    """A record of one tool execution, surfaced to the caller for transparency."""

    tool: str
    arguments: dict[str, object]
    ok: bool


@dataclass(frozen=True)
class AgentResult:
    """The outcome of an agent run: the reply plus an auditable trace."""

    reply: str
    iterations: int
    trace: list[ToolCallTrace]


async def run_agent(
    *,
    provider: LLMProvider,
    service: TaskService,
    user_message: str,
    system_prompt: str,
    max_iterations: int,
) -> AgentResult:
    """Run the model<->tool loop until a final answer or the iteration cap.

    Args:
        provider: the LLM backend (Claude or mock) — programmed against the
            `LLMProvider` Protocol, so this function never knows which it is.
        service: the TaskService the tools act through (caller's authority).
        user_message: the human's request.
        system_prompt: instructions + guardrails for the model.
        max_iterations: hard cap on model<->tool round trips.

    Returns:
        AgentResult with the final reply, iteration count, and tool trace.

    Raises:
        AgentError: if the model never produced a final answer within the cap.
    """
    conversation: list[ConversationItem] = [UserMessage(text=user_message)]
    specs = tool_specs()
    trace: list[ToolCallTrace] = []

    # SYNTAX TIP: `range(max_iterations)` bounds the loop — there is no `while
    #   True`. A hard bound is a non-negotiable safety property for agent loops.
    for iteration in range(1, max_iterations + 1):
        turn = await provider.generate(system=system_prompt, conversation=conversation, tools=specs)
        # Record what the model said/asked this turn.
        conversation.append(AssistantMessage(text=turn.text, tool_calls=turn.tool_calls))

        # No tool calls => the model gave its final answer.
        if not turn.tool_calls:
            logger.info("agent_done", extra={"iterations": iteration, "tools_used": len(trace)})
            return AgentResult(reply=turn.text, iterations=iteration, trace=trace)

        # Otherwise execute every requested tool call and feed results back.
        results = []
        for call in turn.tool_calls:
            result = await dispatch_tool_call(
                service=service, call_id=call.id, name=call.name, arguments=call.arguments
            )
            results.append(result)
            trace.append(
                ToolCallTrace(tool=call.name, arguments=call.arguments, ok=not result.is_error)
            )
        conversation.append(ToolResultsMessage(results=results))

    # We exhausted the iteration budget without a final answer.
    logger.warning("agent_max_iterations", extra={"max_iterations": max_iterations})
    raise AgentError(
        f"The assistant did not finish within {max_iterations} steps. Please simplify the request."
    )
