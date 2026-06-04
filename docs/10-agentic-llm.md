# Module 10 — Agentic / LLM Integration

> **Goal:** understand tool calling, the agent loop, and how to integrate an LLM
> *safely* into a production app.

This is the capstone. Everything before it (layers, the shared service, security,
testing) exists so this part can be both powerful and safe.

## What "agentic" means

A modern LLM can be given a set of **tools** (functions). Instead of answering
directly, it can reply *"please run tool X with these arguments."* Your code runs
the tool and feeds the result back; the model continues, possibly calling more
tools, until it produces a final answer. That cycle is the **agent loop**.

There's no direct Java analog for tool calling. But the *architecture* around it
is familiar: a Strategy pattern behind an interface, plus an allow-list.

## The provider abstraction (Strategy pattern)

We program the loop against a small `Protocol`, not a concrete SDK — see
[`agent/provider.py`](../src/pytegration/agent/provider.py):

```python
@runtime_checkable
class LLMProvider(Protocol):
    async def generate(self, *, system, conversation, tools) -> AssistantTurn: ...
```

A `Protocol` is a **structural** interface: any class with a matching `generate`
satisfies it without declaring `implements` (Java interfaces are *nominal*; this
is "duck typing, type-checked"). Two implementations:

- [`MockProvider`](../src/pytegration/agent/mock_provider.py) — deterministic,
  offline, no key. Makes the whole agent runnable and **testable**.
- [`ClaudeProvider`](../src/pytegration/agent/claude_provider.py) — the real
  Anthropic API with tool use + prompt caching.

A [`factory`](../src/pytegration/agent/factory.py) picks one from config. The loop
can't tell them apart — which is *why* tests can run the agent end-to-end offline.

## The agent loop

See [`agent/loop.py`](../src/pytegration/agent/loop.py):

```
conversation = [user message]
for iteration in range(1, max_iterations + 1):       # ← hard cap (guardrail!)
    turn = await provider.generate(system, conversation, tools)
    append turn to conversation
    if turn has no tool calls:        return final answer
    for each tool call:               execute it safely, collect results
    append tool results to conversation
raise AgentError("did not finish")    # cap exhausted
```

The loop is bounded by `agent_max_iterations` — never `while True`. A hard bound
is a non-negotiable safety property (we test it in
[`tests/evals/`](../tests/evals/test_agent_evals.py)).

## Tools = the security boundary

This is the crux. See [`agent/tools.py`](../src/pytegration/agent/tools.py):

1. **Allow-list:** the model can only call tools in the `TOOLS` registry. No
   "arbitrary code" tool exists.
2. **Re-validation:** the model's argument JSON is untrusted; each call is parsed
   through a Pydantic model (`extra="forbid"`) before running.
3. **Same authority:** every tool delegates to the same `TaskService` the REST API
   uses (Module 4). The agent can do nothing a normal client couldn't.

The tool's JSON Schema (advertised to the model) is **derived from** the same
Pydantic model used to validate — one source of truth, so they can never drift:

```python
ToolSpec(name=..., description=..., input_schema=self.args_model.model_json_schema())
```

A bad or malicious tool call becomes a *recoverable tool error* fed back to the
model, never a crash:

```python
return ToolResult(call_id=..., content=f"Invalid arguments: {exc}", is_error=True)
```

## Prompt caching (real provider)

The system prompt + tool definitions are a large, *unchanging* prefix on every
turn. `ClaudeProvider` marks them with `cache_control`, so Anthropic caches that
prefix and later turns reuse it — cutting latency and cost. Think server-side
memoization of the request prefix.

## Prompt injection — and why allow-lists matter more

Task content the agent reads back (titles, descriptions) is *user data* that might
say *"ignore your instructions."* The system prompt
([`agent/prompts.py`](../src/pytegration/agent/prompts.py)) tells the model to
treat tool output as data, not instructions — but **no prompt is a guarantee**.
The real protection is structural: the model has no dangerous tool to call, and
every argument is validated. Prompt framing is defense-in-depth on top.

## Evals

[`tests/evals/test_agent_evals.py`](../tests/evals/test_agent_evals.py) tests
**behavior**: given a message, did the agent call the right tools and reach the
right outcome? Run against the mock for stable CI; run against the real model on a
schedule (asserting on outcomes, not exact wording) to catch regressions.

## Try it offline

```bash
curl -s -X POST localhost:8000/api/v1/agent/chat \
  -H 'X-API-Key: dev-local' -H 'Content-Type: application/json' \
  -d '{"message":"Create a high priority task to deploy, then summarize my open tasks"}'
```

You'll get a final reply plus a `trace` of exactly which tools ran — observable,
auditable, and entirely offline.

🎉 You've reached the end of the course. Fork this project and build your own.
