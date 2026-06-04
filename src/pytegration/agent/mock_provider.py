"""MockProvider — a deterministic, offline LLM stand-in.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
LAYER:  agent

WHY a mock provider at all?
    Two reasons, both important:
      1. OFFLINE/FREE: the whole agent (endpoint, loop, tools) runs with no API
         key and no network — so anyone can study and run it, and CI stays cheap.
      2. DETERMINISM: real LLMs are non-deterministic, which makes tests flaky.
         A scripted provider lets us assert EXACTLY which tools get called.
    It satisfies the same `LLMProvider` Protocol as the real Claude provider, so
    the agent loop cannot tell them apart — the essence of the Strategy pattern.

WHAT IT IS NOT:
    This is NOT natural-language understanding. It uses crude keyword heuristics
    to decide which tools to call. That is fine: its job is to exercise the loop,
    not to be smart.
"""

from __future__ import annotations

import json
import re

from pytegration.agent.provider import (
    AssistantTurn,
    ConversationItem,
    ToolCall,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)


def _first_user_message(conversation: list[ConversationItem]) -> str:
    """Return the original user request (lowercased) for keyword matching."""
    for item in conversation:
        if isinstance(item, UserMessage):
            return item.text.lower()
    return ""


def _extract_title(text: str) -> str:
    """Best-effort title extraction from a 'create a task ...' style request."""
    # Try "task to <title>" first (e.g. "create a task to deploy the API").
    match = re.search(r"task to ([\w][\w \-]{2,80})", text)
    if match:
        return match.group(1).strip().title()
    # Then "<title> task" (e.g. "create a deploy task"), dropping priority words.
    match = re.search(r"create (?:a |an )?(.*?) task", text)
    if match:
        cleaned = re.sub(r"\b(high|medium|low|priority)\b", "", match.group(1)).strip()
        if cleaned:
            return cleaned.title()
    return "New Task"


def _final_reply(conversation: list[ConversationItem]) -> str:
    """Compose a closing sentence from the most recent tool results."""
    last_results = None
    for item in conversation:
        if isinstance(item, ToolResultsMessage):
            last_results = item

    if last_results is not None:
        for result in last_results.results:
            try:
                payload = json.loads(result.content)
            except (ValueError, TypeError):
                continue
            if "open" in payload and "total" in payload:
                return f"You have {payload['total']} task(s), {payload['open']} still open."
            if "tasks" in payload:
                return f"You currently have {payload.get('total', 0)} task(s)."
    return "Done."


class MockProvider:
    """A scripted provider that drives the agent loop deterministically."""

    async def generate(
        self,
        *,
        system: str,
        conversation: list[ConversationItem],
        tools: list[ToolSpec],
    ) -> AssistantTurn:
        """Decide the next turn from simple keyword intent + how far we've gotten.

        The number of `ToolResultsMessage` items tells us how many tool rounds are
        already done, so we can step through a small plan one tool at a time —
        exactly the shape of a real multi-step agent interaction.
        """
        text = _first_user_message(conversation)
        completed_rounds = sum(isinstance(i, ToolResultsMessage) for i in conversation)

        # Derive a tiny plan from the request.
        plan: list[str] = []
        if re.search(r"\b(create|add|make)\b", text):
            plan.append("create")
        if re.search(r"\b(summar|how many|open task)", text):
            plan.append("summarize")
        elif re.search(r"\b(list|show|what are)\b", text):
            plan.append("list")

        # Still steps left in the plan -> emit the next tool call.
        if completed_rounds < len(plan):
            step = plan[completed_rounds]
            call_id = f"mock-{completed_rounds}"
            if step == "create":
                priority = "high" if "high" in text else "low" if "low" in text else "medium"
                args = {"title": _extract_title(text), "priority": priority}
                return AssistantTurn(text="", tool_calls=[ToolCall(call_id, "create_task", args)])
            if step == "summarize":
                return AssistantTurn(text="", tool_calls=[ToolCall(call_id, "summarize_tasks", {})])
            if step == "list":
                return AssistantTurn(text="", tool_calls=[ToolCall(call_id, "list_tasks", {})])

        # Plan exhausted (or no recognized intent) -> final answer.
        return AssistantTurn(text=_final_reply(conversation), tool_calls=[])
