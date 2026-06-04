"""ClaudeProvider — the real Anthropic Claude backend for the agent.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
LAYER:  agent

This is the production provider. It translates our provider-agnostic conversation
into Anthropic's message format, calls the API with tool use enabled, and parses
the response back into an `AssistantTurn`. Because it satisfies the same
`LLMProvider` Protocol as MockProvider, the agent loop is unchanged.

NOTE ON TYPING: the Anthropic SDK ships precise TypedDicts for request payloads.
    Our provider-agnostic dicts are looser, so a few `# type: ignore[arg-type]`
    annotations bridge the gap. We validate shapes ourselves and the SDK validates
    at the wire, so this is safe; the comments mark exactly where and why.
"""

from __future__ import annotations

from typing import Any, cast

from anthropic import APIError, AsyncAnthropic
from anthropic.types import TextBlock, ToolUseBlock

from pytegration.agent.provider import (
    AssistantMessage,
    AssistantTurn,
    ConversationItem,
    ToolCall,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)
from pytegration.core.errors import AgentError
from pytegration.core.logging import get_logger

logger = get_logger(__name__)

# A conservative output cap. WHY bound it? Output tokens cost money and time; a
# cap is both a budget control and a guard against pathological responses.
_MAX_TOKENS = 1024


class ClaudeProvider:
    """Talks to Anthropic's Messages API with tool use and prompt caching."""

    def __init__(self, *, api_key: str, model: str) -> None:
        # SYNTAX TIP: the async client mirrors the sync one but its calls are
        #   awaitable, so it fits our async stack without blocking the event loop.
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    def _to_anthropic_messages(self, conversation: list[ConversationItem]) -> list[dict[str, Any]]:
        """Translate our conversation items into Anthropic message dicts."""
        messages: list[dict[str, Any]] = []
        for item in conversation:
            if isinstance(item, UserMessage):
                messages.append({"role": "user", "content": [{"type": "text", "text": item.text}]})
            elif isinstance(item, AssistantMessage):
                content: list[dict[str, Any]] = []
                if item.text:
                    content.append({"type": "text", "text": item.text})
                for call in item.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": call.id,
                            "name": call.name,
                            "input": call.arguments,
                        }
                    )
                messages.append({"role": "assistant", "content": content})
            elif isinstance(item, ToolResultsMessage):
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": result.call_id,
                                "content": result.content,
                                "is_error": result.is_error,
                            }
                            for result in item.results
                        ],
                    }
                )
        return messages

    def _to_anthropic_tools(self, tools: list[ToolSpec]) -> list[dict[str, Any]]:
        """Translate tool specs, marking the last one for prompt caching."""
        wire_tools: list[dict[str, Any]] = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        # PROMPT CACHING: marking the final tool with cache_control caches the
        #   system prompt + all tool definitions (the big, unchanging prefix).
        #   Subsequent turns in the same conversation reuse that cached prefix,
        #   cutting latency and cost. JAVA NOTE: think of it as a server-side
        #   memoization of the request prefix.
        if wire_tools:
            wire_tools[-1]["cache_control"] = {"type": "ephemeral"}
        return wire_tools

    async def generate(
        self,
        *,
        system: str,
        conversation: list[ConversationItem],
        tools: list[ToolSpec],
    ) -> AssistantTurn:
        """Call Claude once and parse the result into an AssistantTurn."""
        # The system prompt is sent as a cacheable block (stable across turns).
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system_blocks,  # type: ignore[arg-type]
                messages=self._to_anthropic_messages(conversation),  # type: ignore[arg-type]
                tools=self._to_anthropic_tools(tools),  # type: ignore[arg-type]
            )
        except APIError as exc:
            # SECURITY: log the failure server-side but raise a generic AgentError
            #   so we never leak provider internals to the API client.
            logger.error("claude_api_error", exc_info=exc)
            raise AgentError("The AI provider is currently unavailable.") from exc

        # Parse Claude's response blocks into our provider-agnostic turn.
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif isinstance(block, ToolUseBlock):
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=cast(dict[str, Any], block.input),
                    )
                )

        return AssistantTurn(text="".join(text_parts), tool_calls=tool_calls)
