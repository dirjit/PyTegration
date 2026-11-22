"""Agent endpoint — talk to the task assistant.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
LAYER:  api

This route is intentionally thin: it injects a provider + service, runs the agent
loop, and maps the result to the response schema. All the interesting logic lives
in agent/loop.py and agent/tools.py.
"""

from __future__ import annotations

from fastapi import APIRouter

from pytegration.agent.guide_tools import guide_toolbox
from pytegration.agent.loop import AgentResult, run_agent
from pytegration.agent.prompts import GUIDE_SYSTEM_PROMPT, SYSTEM_PROMPT
from pytegration.agent.tools import task_toolbox
from pytegration.api.deps import CosmosServiceDep, ProviderDep, SettingsDep, TaskServiceDep
from pytegration.schemas.agent import AgentRequest, AgentResponse, GuideRequest, ToolCallTrace

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
        toolbox=task_toolbox(service),
        user_message=payload.message,
        system_prompt=SYSTEM_PROMPT,
        max_iterations=settings.agent_max_iterations,
    )
    return _to_response(result)


@router.post("/guide", response_model=AgentResponse, summary="Ask Nova, the kids' Space Guide")
async def guide(
    payload: GuideRequest,
    provider: ProviderDep,
    cosmos: CosmosServiceDep,
    settings: SettingsDep,
) -> AgentResponse:
    """Answer a child's space question with grounded, read-only tools.

    Same loop, different toolbox + system prompt: that is the whole difference
        between "task assistant" and "space guide". (See agent/toolbox.py.)
    SECURITY: unlike the public /cosmos atlas, this endpoint calls an LLM (real
        cost, free-text output), so it stays behind the API key and rate limit.
    """
    result = await run_agent(
        provider=provider,
        toolbox=guide_toolbox(cosmos),
        user_message=payload.message,
        system_prompt=GUIDE_SYSTEM_PROMPT,
        max_iterations=settings.agent_max_iterations,
    )
    return _to_response(result)


def _to_response(result: AgentResult) -> AgentResponse:
    """Map the loop's internal result to the API schema."""
    return AgentResponse(
        reply=result.reply,
        iterations=result.iterations,
        trace=[ToolCallTrace(tool=t.tool, arguments=t.arguments, ok=t.ok) for t in result.trace],
    )
