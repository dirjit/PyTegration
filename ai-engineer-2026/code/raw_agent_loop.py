"""raw_agent_loop.py — Phase 1: the agent loop, from scratch, no magic.

> **Goal:** see the entire agent loop with nothing hidden — call the model with
> messages + tools, parse the tool-use blocks it returns, execute the tool,
> append the result, and loop until the model stops.

This is the "CPU instruction cycle" of every agent you'll ever build. Frameworks
(LangGraph, the Claude Agent SDK, Deep Agents) wrap this loop in convenience, but
the loop *is the same loop*. Type it once by hand and every framework becomes
readable (curriculum README: "teaches the primitives so any framework becomes
readable").

Mapping to the 4 context primitives (Lesson 04):
  - WRITE   -> the `write_file` tool persists state OUTSIDE the window (a memory
              file on disk that survives steps).
  - SELECT  -> the `web_search` / `read_file` tools pull the RIGHT tokens in at the
              point of use, instead of dumping everything upfront.
  - COMPRESS-> not shown here (see mini_harness/context.py) — would summarize when
              the window approaches ~85% full.
  - ISOLATE -> not shown here (see mini_harness/subagents.py) — would spawn a
              sub-agent with its own clean window.

Runs with NO API KEY: the default `MockProvider` is deterministic and offline.
Swap in `AnthropicProvider` (commented stub at the bottom) for the real thing.

    $ python raw_agent_loop.py        # works with only stdlib + asyncio

Stdlib only. No third-party imports at module load time.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

# ─────────────────────────────────────────────────────────────────────────────
# 1. The tool registry: a tiny @tool decorator that captures name / description /
#    JSON-schema from a function's signature and docstring.
#
#    A "tool" the model can call is just: a name, a human description, a JSON
#    schema for its arguments, and a Python callable that does the work. The
#    decorator below derives the schema from type hints so you write each tool
#    once, as an ordinary function.
# ─────────────────────────────────────────────────────────────────────────────

# Map Python annotations -> JSON-schema types. Kept deliberately small; a real
# harness (mini_harness/tools.py) handles more types and validation.
_PY_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


@dataclass
class Tool:
    """A registered tool: its schema (for the model) + its impl (for the harness)."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema, the `input_schema` the API expects
    func: Callable[..., Awaitable[str]]

    def schema(self) -> dict[str, Any]:
        """The shape an LLM API expects in its `tools=[...]` argument."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


# The registry. In a real harness you might have several scoped registries; here
# one global dict keeps the example legible.
REGISTRY: dict[str, Tool] = {}


def tool(func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    """Decorator: register an async function as a tool.

    Derives the JSON schema from the function's type hints, and the description
    from its docstring's first line. Every parameter without a default is marked
    `required`. This is the same idea the SDK's `@beta_tool` decorator automates —
    we do it by hand so you can see there's no magic.
    """
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for pname, param in sig.parameters.items():
        annotation = param.annotation
        json_type = _PY_TO_JSON.get(annotation, "string")  # default to string
        properties[pname] = {"type": json_type, "description": f"{pname} argument"}
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    description = (func.__doc__ or func.__name__).strip().split("\n", 1)[0]
    REGISTRY[func.__name__] = Tool(
        name=func.__name__,
        description=description,
        parameters={
            "type": "object",
            "properties": properties,
            "required": required,
        },
        func=func,
    )
    return func


# ─────────────────────────────────────────────────────────────────────────────
# 2. The three example tools.
#
#    `read_file` / `write_file` are REAL — but sandboxed to a temp working dir so
#    the demo can't touch the rest of your disk (a baby version of the
#    sandboxing discipline in mini_harness/sandbox.py).
#    `web_search` is MOCKED (returns canned text) so the file runs offline.
# ─────────────────────────────────────────────────────────────────────────────

# The sandbox root. All file tools resolve paths *inside* this directory and
# refuse anything that escapes it. SECURITY: never let a model-supplied path
# reach the raw filesystem — always resolve and confine it.
SANDBOX = Path(tempfile.mkdtemp(prefix="agent_sandbox_"))


def _safe_path(relative: str) -> Path:
    """Resolve `relative` inside SANDBOX, refusing path-traversal escapes.

    SECURITY: a model can (and in adversarial settings *will*) emit
    `../../etc/passwd`. We resolve the path and assert it stays under SANDBOX.
    """
    candidate = (SANDBOX / relative).resolve()
    if not candidate.is_relative_to(SANDBOX.resolve()):
        raise ValueError(f"path escapes sandbox: {relative!r}")
    return candidate


@tool
async def web_search(query: str) -> str:
    """Search the web for a query and return the top results as text.

    (MOCK: returns canned text so the file runs with no network / no API key.
    This is the SELECT primitive — pull relevant tokens in at the point of use.)
    """
    # A real implementation would call a search API. We key off the query so the
    # demo feels responsive without ever leaving the process.
    canned = {
        "harness": (
            "A 'harness' is everything between your code and the raw model API: "
            "the agent loop, tool dispatch, context assembly, memory, sandboxing, "
            "observability, and evals. The same model on a good vs. bad harness "
            "can swing 10-36 points on agent benchmarks."
        ),
    }
    for key, text in canned.items():
        if key in query.lower():
            return f"[search results for {query!r}]\n{text}"
    return f"[search results for {query!r}]\nNo strong match; try a narrower query."


@tool
async def write_file(path: str, content: str) -> str:
    """Write text to a file inside the sandbox (the WRITE primitive: durable memory)."""
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {path}"


@tool
async def read_file(path: str) -> str:
    """Read text from a file inside the sandbox (the SELECT primitive: just-in-time)."""
    target = _safe_path(path)
    if not target.exists():
        return f"error: {path} does not exist"
    return target.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 3. The provider boundary.
#
#    `LLMProvider` is the seam between the harness and any model API. Code against
#    the Protocol and the loop is provider-agnostic — mock for offline tests,
#    Anthropic for production, anything else later.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ModelResponse:
    """A normalized model turn. `stop_reason` drives the loop.

    `content` is a list of blocks. Two block shapes matter to the loop:
      {"type": "text", "text": ...}
      {"type": "tool_use", "id": ..., "name": ..., "input": {...}}
    This mirrors the Anthropic Messages API content blocks so the real provider
    is a thin translation.
    """

    content: list[dict[str, Any]]
    stop_reason: str  # "tool_use" -> execute tools and loop; "end_turn" -> done


class LLMProvider(Protocol):
    """The one method every provider implements. Code to this, not to a vendor."""

    async def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        """Given the conversation + tool schemas, return the next model turn."""
        ...


class MockProvider:
    """A deterministic, offline provider — no API key, no network.

    It runs a fixed *script*: search -> write a memory file -> read it back -> finish.
    That exercises every branch of the loop (tool calls, tool results, stop) so you
    can watch the mechanics without paying for tokens. Real model behavior is
    non-deterministic; this is a stand-in for teaching and for fast tests.
    """

    def __init__(self) -> None:
        self._step = 0

    async def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        # The script is keyed purely on how many turns we've taken. A real model
        # would instead read `messages` (including the tool_results we appended)
        # and decide what to do next.
        self._step += 1

        if self._step == 1:
            return ModelResponse(
                stop_reason="tool_use",
                content=[
                    {"type": "text", "text": "Let me research what a harness is."},
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "web_search",
                        "input": {"query": "what is an agent harness"},
                    },
                ],
            )
        if self._step == 2:
            return ModelResponse(
                stop_reason="tool_use",
                content=[
                    {"type": "text", "text": "Saving findings to memory."},
                    {
                        "type": "tool_use",
                        "id": "call_2",
                        "name": "write_file",
                        "input": {
                            "path": "findings.md",
                            "content": "# Findings\nA harness is the system around the model.",
                        },
                    },
                ],
            )
        if self._step == 3:
            return ModelResponse(
                stop_reason="tool_use",
                content=[
                    {"type": "text", "text": "Reading findings back to confirm."},
                    {
                        "type": "tool_use",
                        "id": "call_3",
                        "name": "read_file",
                        "input": {"path": "findings.md"},
                    },
                ],
            )
        # Final turn: no tool calls, the model is done.
        return ModelResponse(
            stop_reason="end_turn",
            content=[
                {
                    "type": "text",
                    "text": (
                        "Done. A harness is everything between your code and the "
                        "model API; I saved the finding to findings.md."
                    ),
                }
            ],
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. The loop itself.
#
#    This is the whole job. Everything else in the curriculum makes THIS reliable,
#    observable, cheap, and safe.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AgentResult:
    final_text: str
    iterations: int
    trace: list[str] = field(default_factory=list)


async def run_agent(
    *,
    provider: LLMProvider,
    system: str,
    task: str,
    max_iterations: int = 10,
) -> AgentResult:
    """Drive the model->tools->model cycle until it stops — or until the hard cap.

    HARD CAP (`max_iterations`): this is the single most important guardrail in
    an agent. Without it, one confused model that keeps calling tools is an
    *unbounded* bill and an *infinite* loop at 2am. The curriculum's thesis is
    that the harness — not the model — is the job, and a bounded loop is the
    first thing the harness owes you. Treat hitting the cap as a FAILURE to
    investigate, never as normal completion.
    """
    tools = [t.schema() for t in REGISTRY.values()]

    # The conversation. The API is stateless — we resend the whole history each
    # turn (Lesson: context engineering = curating every token every step).
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]

    trace: list[str] = []

    def log(line: str) -> None:
        trace.append(line)
        print(line)

    log(f"── TASK ──\n{task}\n")
    log(f"(sandbox working dir: {SANDBOX})\n")

    for iteration in range(1, max_iterations + 1):
        log(f"── ITERATION {iteration}/{max_iterations} ──")

        # 1) Call the model with the full context + the tool schemas.
        response = await provider.generate(system=system, messages=messages, tools=tools)

        # Show any text the model produced this turn.
        for block in response.content:
            if block["type"] == "text":
                log(f"  model: {block['text']}")

        # 2) If the model didn't ask for tools, it's finished. Return.
        if response.stop_reason != "tool_use":
            final = next((b["text"] for b in response.content if b["type"] == "text"), "")
            log(f"\n── DONE in {iteration} iteration(s) ──")
            return AgentResult(final_text=final, iterations=iteration, trace=trace)

        # 3) Append the assistant turn VERBATIM (tool_use blocks and all) — the
        #    next request must contain them so tool_results can reference their ids.
        messages.append({"role": "assistant", "content": response.content})

        # 4) Execute every requested tool and collect results.
        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if block["type"] != "tool_use":
                continue
            name, args, call_id = block["name"], block["input"], block["id"]
            log(f"  -> tool_use: {name}({json.dumps(args)})")

            tool_obj = REGISTRY.get(name)
            if tool_obj is None:
                # Tell the model its call was invalid rather than crashing the loop.
                result_text, is_error = f"error: unknown tool {name!r}", True
            else:
                try:
                    result_text, is_error = await tool_obj.func(**args), False
                except Exception as exc:  # surface tool failures back to the model
                    result_text, is_error = f"error: {exc}", True

            preview = result_text if len(result_text) <= 200 else result_text[:200] + "…"
            log(f"  ← tool_result{' [ERROR]' if is_error else ''}: {preview}")

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": result_text,
                    "is_error": is_error,
                }
            )

        # 5) Feed the tool results back as a user turn, then loop.
        messages.append({"role": "user", "content": tool_results})
        log("")

    # Fell out of the loop without stopping -> we hit the hard cap.
    log(f"\n── STOPPED: hit max_iterations={max_iterations} (guardrail) ──")
    return AgentResult(
        final_text="(stopped: hit iteration cap before finishing)",
        iterations=max_iterations,
        trace=trace,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. The real provider — a COMMENTED STUB.
#
#    This is exactly where the production Anthropic SDK call goes. It's commented
#    out so this file imports and runs with no SDK installed and no API key. To go
#    live: `pip install anthropic`, set ANTHROPIC_API_KEY, and uncomment.
#
#    AUTH BROKERING (curriculum): the key is read from the environment by the SDK
#    — it is NEVER hardcoded and NEVER passed to a tool or into the sandbox. The
#    harness brokers credentials; model-controlled code never sees them.
# ─────────────────────────────────────────────────────────────────────────────

# class AnthropicProvider:
#     """Production provider backed by the Anthropic Messages API.
#
#     Defaults to Claude Opus 4.8 with adaptive thinking (the recommended setting
#     for agentic work). The loop above is unchanged — only this class differs
#     between offline tests and production. That's the payoff of the Protocol seam.
#     """
#
#     def __init__(self, model: str = "claude-opus-4-8") -> None:
#         import anthropic  # imported lazily so the stdlib-only demo never needs it
#
#         # The SDK resolves ANTHROPIC_API_KEY from the environment. Do not
#         # hardcode a key. (Auth brokering: credentials stay in the harness.)
#         self._client = anthropic.AsyncAnthropic()
#         self._model = model
#
#     async def generate(
#         self,
#         *,
#         system: str,
#         messages: list[dict[str, Any]],
#         tools: list[dict[str, Any]],
#     ) -> ModelResponse:
#         resp = await self._client.messages.create(
#             model=self._model,
#             max_tokens=4096,
#             system=system,
#             messages=messages,
#             tools=tools,
#             thinking={"type": "adaptive"},          # recommended for Opus 4.8
#             output_config={"effort": "high"},       # high effort for agentic work
#         )
#         # Translate the SDK's typed content blocks into our plain-dict shape.
#         content: list[dict[str, Any]] = []
#         for block in resp.content:
#             if block.type == "text":
#                 content.append({"type": "text", "text": block.text})
#             elif block.type == "tool_use":
#                 content.append(
#                     {
#                         "type": "tool_use",
#                         "id": block.id,
#                         "name": block.name,
#                         "input": block.input,
#                     }
#                 )
#             # (thinking blocks omitted here for brevity; preserve them in prod
#             #  if you stream reasoning to users.)
#         return ModelResponse(content=content, stop_reason=resp.stop_reason)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Demo entry point. `python raw_agent_loop.py` runs a research task end-to-end
#    on the offline MockProvider.
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a research agent. Use web_search to find information, write_file to "
    "save durable findings, and read_file to recall them. Finish with a short "
    "summary once the question is answered."
)


async def _main() -> None:
    provider: LLMProvider = MockProvider()  # swap for AnthropicProvider() to go live
    result = await run_agent(
        provider=provider,
        system=SYSTEM_PROMPT,
        task="What is an agent 'harness'? Research it and save the finding.",
        max_iterations=10,  # the guardrail
    )
    print("\n══ FINAL ANSWER ══")
    print(result.final_text)
    print(f"\n(completed in {result.iterations} iteration(s))")


if __name__ == "__main__":
    asyncio.run(_main())
