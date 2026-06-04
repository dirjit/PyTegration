"""Agent endpoint — talk to the task assistant.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
LAYER:  api

This route is intentionally thin: it injects a provider + service, runs the agent
loop, and maps the result to the response schema. All the interesting logic lives
in agent/loop.py and agent/tools.py.
"""

from __future__ import annotations

from fastapi import APIRouter

from pytegration.agent.loop import run_agent
from pytegration.agent.prompts import SYSTEM_PROMPT
from pytegration.api.deps import ProviderDep, SettingsDep, TaskServiceDep
from pytegration.schemas.agent import AgentRequest, AgentResponse, ToolCallTrace

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=AgentResponse, summary="Chat with the task assistant")
async def chat(
    payload: AgentRequest,
    provider: ProviderDep,
    service: TaskServiceDep,
    settings: SettingsDep,
) -> AgentResponse:
    """Run the agent loop for one user message and return its reply + trace.

    SECURITY: the agent acts through the injected `service`, so it has exactly the
        caller's authority — the same TaskService the REST API uses. The iteration
        cap (`settings.agent_max_iterations`) bounds cost and prevents runaway loops.
    """
    result = await run_agent(
        provider=provider,
        service=service,
        user_message=payload.message,
        system_prompt=SYSTEM_PROMPT,
        max_iterations=settings.agent_max_iterations,
    )
    return AgentResponse(
        reply=result.reply,
        iterations=result.iterations,
        # Map the loop's internal trace records to the API schema.
        trace=[ToolCallTrace(tool=t.tool, arguments=t.arguments, ok=t.ok) for t in result.trace],
    )
