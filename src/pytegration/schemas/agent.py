"""Agent API contracts — request and response DTOs for the assistant endpoint.

LESSON: Module 3 / Module 10. See docs/10-agentic-llm.md
LAYER:  schemas
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AgentRequest(BaseModel):
    """Body for POST /agent/chat — a single natural-language instruction."""

    model_config = ConfigDict(extra="forbid")

    # SECURITY: bound the input length. Unbounded prompts are a cost/abuse vector
    #   for any LLM endpoint.
    message: str = Field(
        min_length=1,
        max_length=4000,
        examples=["Create a high priority task to deploy, then summarize my open tasks"],
    )


class ToolCallTrace(BaseModel):
    """One tool the agent executed, exposed for transparency/auditability."""

    model_config = ConfigDict(frozen=True)

    tool: str
    arguments: dict[str, object]
    ok: bool


class AgentResponse(BaseModel):
    """The assistant's final reply plus an auditable trace of what it did.

    WHY return the trace? Agent behavior should be observable. Surfacing the tools
        it called (and whether each succeeded) makes the agent debuggable and
        builds user trust — they can SEE that "summarize" really ran.
    """

    reply: str
    iterations: int = Field(description="Number of model<->tool round trips taken.")
    trace: list[ToolCallTrace]
