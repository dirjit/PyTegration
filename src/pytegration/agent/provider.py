"""LLM provider abstraction — a provider-agnostic interface for tool-using chat.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
LAYER:  agent

WHY abstract the provider?
    The agent loop should not care whether it is talking to Claude, a mock, or
    some future model. We define a small `Protocol` and a handful of plain data
    types here; the loop programs against THOSE, and each concrete provider
    (claude_provider.py, mock_provider.py) translates to/from its own wire format.
    This is what lets the entire agent run offline against the mock in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# =============================================================================
# Provider-agnostic data types (the shared vocabulary of the agent layer).
# =============================================================================
# SYNTAX TIP: `@dataclass(frozen=True)` gives us immutable, value-comparable
#   records (like Java `record`s). Using frozen records for messages makes the
#   conversation history safe to pass around without fear of accidental mutation.


@dataclass(frozen=True)
class ToolSpec:
    """A tool advertised to the model: name, description, and JSON-Schema inputs.

    The `input_schema` is a JSON Schema dict describing the tool's arguments. The
    model uses it to produce well-formed calls; we ALSO re-validate against it
    (and a Pydantic model) before executing — never trust model output blindly.
    """

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """A request from the model to run one tool with the given arguments."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """The outcome of running a tool, to be fed back to the model."""

    call_id: str
    content: str  # serialized result (we use JSON text)
    is_error: bool = False


@dataclass(frozen=True)
class AssistantTurn:
    """What the model produced in a single turn.

    If `tool_calls` is empty, the model is DONE and `text` is the final answer.
    Otherwise the loop must execute the calls and continue the conversation.
    """

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


# ----- Conversation items (the running history we send each turn) -------------


@dataclass(frozen=True)
class UserMessage:
    """A message authored by the human user."""

    text: str


@dataclass(frozen=True)
class AssistantMessage:
    """A prior assistant turn (text and/or the tool calls it requested)."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ToolResultsMessage:
    """The results of the tool calls from the preceding assistant message."""

    results: list[ToolResult]


# SYNTAX TIP: a union type alias. `X | Y | Z` is the modern (3.10+) way to write
#   `Union[...]`. Conversation history is a list of these three shapes.
ConversationItem = UserMessage | AssistantMessage | ToolResultsMessage


# =============================================================================
# The provider interface.
# =============================================================================
# SYNTAX TIP: a `Protocol` defines a STRUCTURAL interface — any class with a
#   matching `generate` method satisfies it, WITHOUT explicitly subclassing.
#   JAVA NOTE: Java interfaces are NOMINAL (a class must declare `implements`).
#   Python Protocols are "duck typing with a type checker": mypy verifies the
#   shape. `@runtime_checkable` additionally allows `isinstance(x, LLMProvider)`.
@runtime_checkable
class LLMProvider(Protocol):
    """Anything that can turn a conversation (+ tools) into the next turn."""

    async def generate(
        self,
        *,
        system: str,
        conversation: list[ConversationItem],
        tools: list[ToolSpec],
    ) -> AssistantTurn:
        """Produce the assistant's next turn given the full context.

        Args:
            system: the system prompt (instructions + guardrails).
            conversation: the full message history so far.
            tools: the tools the model is allowed to call.

        Returns:
            The model's next turn: either final text, or tool calls to execute.
        """
        ...
