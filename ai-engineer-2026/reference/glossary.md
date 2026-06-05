# Glossary

> **Goal:** one authoritative, alphabetized definition for every load-bearing term
> in the curriculum. Each entry is 1–3 sentences. Where a term has a home lesson,
> it's linked.

Terms are cross-linked to lessons with relative paths like
[`../curriculum/phase-0-mental-models/04-harness-and-context-primitives.md`](../curriculum/phase-0-mental-models/04-harness-and-context-primitives.md).
When a term builds on another, the related term is **bolded**.

---

### Agent
A system where the **model** decides its own next step in a loop — choosing tools,
reading results, and continuing until done — rather than following a fixed,
code-controlled sequence. Contrast with **workflow**. See
[Phase 0, Lesson 02](../curriculum/phase-0-mental-models/02-workflow-vs-agent.md).

### Agent loop
The core cycle: call the model → if it requests tools, execute them → feed the
**tool_result** back → repeat until the model stops asking for tools. Everything
called a "framework" is this loop plus persistence, routing, and recovery.

### Attention
The transformer mechanism by which each **token**'s representation is influenced by
("attends to") every other token in the window, learning which prior tokens matter
for predicting the next one. The one-sentence intuition: the model reweighs the
entire visible context to predict the next token. See
[Phase 0, Lesson 01](../curriculum/phase-0-mental-models/01-how-llms-behave.md).

### Auth brokering
The harness pattern of holding credentials *outside* the model's reach and
injecting them only when a tool call actually leaves the **sandbox**, so the model
(and anything it generates) never sees a secret. Protects against exfiltration
under **prompt injection**.

### Batch API
An asynchronous endpoint for processing many model requests at once, typically at
a discount and with higher latency tolerance — use it for non-interactive bulk
work (offline evals, large extraction jobs), not user-facing requests.

### Checkpointing
Persisting an agent's full state at each step so a run can resume after a crash,
be inspected, or be replayed. The foundation of **durable execution** and
time-travel debugging (e.g. LangGraph's PostgresSaver).

### Compaction
The act of summarizing or pruning conversation history when the **context window**
approaches full (typically 85–95%), replacing bulky history with a compact summary
so the agent can keep going. The runtime expression of the **Compress** context
primitive.

### Context engineering
Engineering *every token in front of the model at every step* — system prompt,
tools, history, retrieved data, tool results — rather than tweaking a single
prompt. **Prompt engineering** is now a sub-skill of this. See the
[README](../README.md) and
[Phase 0, Lesson 04](../curriculum/phase-0-mental-models/04-harness-and-context-primitives.md).

### Context primitives (Write / Select / Compress / Isolate)
The four — and only four — moves you can make on a context window. **Write**:
persist state outside the window (scratchpad/memory). **Select**: pull in only the
tokens needed now (retrieval, on-demand reads). **Compress**: summarize when the
window fills (**compaction**). **Isolate**: give a sub-task its own window via a
**sub-agent**. See
[Phase 0, Lesson 04](../curriculum/phase-0-mental-models/04-harness-and-context-primitives.md).

### Context window
The maximum number of **tokens** the model can attend to at once — system prompt +
tools + history + tool results + the reply being generated, all of it. It is
finite and is the single most important resource an AI engineer manages. See
[Phase 0, Lesson 01](../curriculum/phase-0-mental-models/01-how-llms-behave.md).

### Context rot / lost-in-the-middle
The reliable tendency of models to attend best to the **start and end** of a long
context and get fuzzier in the **middle**. More context is not automatically
better — relevant, well-*placed* context is. This is *why* the Compress and
Isolate primitives exist.

### Durable execution
The property that an agent's run survives crashes, restarts, and interruptions by
persisting state at every step (**checkpointing**) and resuming where it left off —
"doesn't break at 2am on a Friday." A headline feature of LangGraph. See
[Phase 2](../curriculum/phase-2-production-architecture/).

### Eval (single-turn, trajectory, LLM-as-judge, end-state)
A test of agent quality. **Single-turn**: grade one input→output pair.
**Trajectory**: grade the *sequence* of steps the agent took. **LLM-as-judge**:
use a model to score outputs against a rubric. **End-state**: grade the final world
state (did the file get written correctly?), not the exact text. The heart of
[Phase 4](../curriculum/phase-4-evals-and-regression/).

### Few-shot
Putting a handful of input→output examples in the **context** so the model mimics
the pattern — behavior change at runtime with no training. An instance of
**in-context learning**.

### Fine-tuning
Updating the model's weights by training on your data. Reach for it only after
you've exhausted **context engineering** and measured a real gap — it costs
training infrastructure and gives up the flexibility of **in-context learning**.

### Golden dataset
A curated, trusted set of inputs paired with known-good expected outcomes, used as
the ground truth your **evals** grade against and your **regression gate** defends.
The deliverable of [Phase 4](../curriculum/phase-4-evals-and-regression/).

### GAIA
A benchmark of **general assistant / agent tasks** — multi-step questions needing
tool use, reasoning, and navigation, graded against a single correct answer. See
[reference/benchmarks.md](benchmarks.md).

### Guardrail
A check — code or model-based — that constrains what an agent can do or say:
input validation, output filtering, allow/deny policies, confirmation gates.
Often implemented as a **hook**. See
[Phase 5](../curriculum/phase-5-production-hardening/).

### Hallucination
The model's default behavior of producing a *plausible* continuation rather than a
*true* one — confident, well-formed, and wrong. You engineer around it (retrieval,
tools, **evals**); you do not prompt it away. See
[Phase 0, Lesson 01](../curriculum/phase-0-mental-models/01-how-llms-behave.md).

### Harness
Everything between you and the raw model API: the **agent loop**, tool dispatch,
**context engineering**, memory, persistence, **sandboxing**, observability, and
**evals**. The harness — not the model — is the job. See the [README](../README.md).

### Hook (PreToolUse / PostToolUse / PreCompact / Stop)
Deterministic code that fires at fixed lifecycle points in a harness. **PreToolUse**:
before a tool runs (gate/validate). **PostToolUse**: after (audit/transform).
**PreCompact**: before **compaction** (preserve what matters). **Stop**: when the
agent finishes (cleanup/finalize). The mechanism behind **guardrails** and
**auth brokering**.

### Human-in-the-loop (HITL)
Inserting a human decision point into the agent loop — typically approving a
hard-to-reverse action (send, delete, pay) before it executes. Implemented via a
confirmation **guardrail** / **hook**.

### In-context learning
The model's ability to change behavior *at runtime* purely from what's in the
**context window** — examples, instructions, retrieved data — with no retraining.
The reason **context engineering** beats **fine-tuning** as the default. See
[Phase 0, Lesson 01](../curriculum/phase-0-mental-models/01-how-llms-behave.md).

### Isolation / sub-agent
Giving a sub-task its **own** fresh context window by spawning a worker agent, so
its work doesn't pollute (or get polluted by) the parent's context. The **Isolate**
context primitive. See
[Phase 0, Lesson 04](../curriculum/phase-0-mental-models/04-harness-and-context-primitives.md).

### LangGraph
A production framework that models an agent as an explicit **state machine** (nodes
+ edges), with **durable execution** via a checkpointer, time-travel debugging, and
OTEL-friendly observability. The curriculum's reference production framework. See
[reference/the-stack.md](the-stack.md).

### LLM-as-judge
Using a model to grade another model's output against a rubric — scalable but
needs calibration against human judgment to be trustworthy. One of the four
**eval** types. See [Phase 4](../curriculum/phase-4-evals-and-regression/).

### Middleware
A pluggable layer that wraps the agent loop to add a cross-cutting behavior —
planning, context compression, logging — without rewriting the core. Deep Agents'
planning step is planning **middleware**.

### MCP (Model Context Protocol)
An open protocol for connecting models to external tools, data, and prompts through
a standard interface, so a tool server can be reused across agents and harnesses
instead of being hand-wired each time.

### Orchestrator-worker
A multi-agent pattern where one **orchestrator** agent decomposes a task and
delegates sub-tasks to **worker** (sub-)agents, then composes their results — a
concrete use of **isolation**. See
[Phase 0, Lesson 03](../curriculum/phase-0-mental-models/03-five-workflow-patterns.md).

### Progressive disclosure
Loading detail only when it's needed — e.g. a **skill**'s short description sits in
context by default, and the full instructions are read only when the task calls for
it. Keeps the fixed context small. An application of the **Select** primitive.

### Prompt caching
Reusing the model's processing of a stable prompt prefix across requests to cut cost
and latency. Caching is a *prefix match*: any byte change anywhere in the prefix
invalidates everything after it, so keep stable content first and volatile content
last. See [Phase 5](../curriculum/phase-5-production-hardening/).

### Prompt chaining
A **workflow** pattern that breaks a task into a fixed sequence of model calls, each
feeding the next — predictable and debuggable, no model-driven control flow. See
[Phase 0, Lesson 03](../curriculum/phase-0-mental-models/03-five-workflow-patterns.md).

### Prompt injection
An attack where malicious instructions hidden in tool results, documents, or user
input hijack the agent's behavior. Defended with **sandboxing**, **auth brokering**,
trusted operator channels, and **guardrails** — never by asking the model to be
careful. See [Phase 5](../curriculum/phase-5-production-hardening/).

### Quantization
Reducing the numeric precision of a model's weights (e.g. to 8- or 4-bit) to shrink
memory and speed inference, at some quality cost — central to running an **SLM** on
edge/mobile hardware. See
[Project 1](../projects/01-edge-slm-mobile-app.md).

### RAG
Retrieval-Augmented Generation: fetching relevant documents at query time and
placing them in the **context** so the model answers from grounded facts instead of
**hallucinating**. The first-class expression of the **Select** primitive — but
don't build a vector store before you've measured a recall problem.

### ReAct
An agent pattern interleaving **rea**soning and **act**ing — the model thinks, takes
a tool action, observes the result, and reasons again. The conceptual ancestor of
the modern **agent loop**.

### Regression gate
A CI check that runs your **evals** against a **golden dataset** and **blocks** a
change (new prompt, new model, new code) if it makes quality worse — so "better on
the benchmark" can't silently regress *your* task. The Phase 4 deliverable. See
[Phase 4](../curriculum/phase-4-evals-and-regression/).

### Routing
A **workflow** pattern that classifies an input and sends it down one of several
specialized paths (e.g. a triage step picking the right handler). See
[Phase 0, Lesson 03](../curriculum/phase-0-mental-models/03-five-workflow-patterns.md).

### Sandboxing
Running an agent's tool execution (bash, code, file ops) in an isolated environment
so it can't touch the host, leak data, or cause irreversible harm. A core safety
boundary; pairs with **auth brokering**. See
[Phase 5](../curriculum/phase-5-production-hardening/).

### Skill (SKILL.md)
A folder of task-specific instructions (named by its `SKILL.md`) that the agent
loads **on demand** when relevant, rather than carrying in the base prompt — an
application of **progressive disclosure** and the **Select** primitive.

### SLM (small language model)
A compact model small enough to run with tight resource budgets — on a phone, at the
edge, or cheaply at scale — usually via **quantization**. The focus of
[Project 1](../projects/01-edge-slm-mobile-app.md).

### State machine
A model of computation as explicit states and transitions. **LangGraph** treats an
agent as one (nodes = steps, edges = transitions), making control flow readable,
diffable, and resumable instead of buried in prompt strings.

### SWE-bench
A coding benchmark where an agent must resolve **real GitHub issues** so the repo's
hidden tests pass; **SWE-bench Verified** is the human-filtered, confirmed-solvable
subset. See [reference/benchmarks.md](benchmarks.md).

### tau-bench (τ-bench)
A benchmark for **tool-use customer-service agents** acting in a simulated domain
under policy, against a simulated user — measures multi-turn tool-use reliability.
See [reference/benchmarks.md](benchmarks.md).

### Temperature
The sampling parameter controlling randomness: low (≈0) favors the most likely
**token** (focused, near-deterministic); higher is more varied and more
error-prone. Even at 0, outputs aren't guaranteed bit-for-bit identical. See
[Phase 0, Lesson 01](../curriculum/phase-0-mental-models/01-how-llms-behave.md).

### Token
The sub-word chunk the model actually sees (≈4 characters / ≈0.75 English words).
Cost, **context window** size, and rate limits are all counted in tokens — not
words. See
[Phase 0, Lesson 01](../curriculum/phase-0-mental-models/01-how-llms-behave.md).

### Tool / tool dispatch / tool_use / tool_result
A **tool** is a function the model can invoke (with a name + input schema). **Tool
dispatch** is the harness routing a requested call to the right code. **tool_use**
is the model's request block ("call `X` with these args"); **tool_result** is the
block carrying the execution output back into context, matched by `tool_use_id`.

### Trajectory
The full sequence of steps an agent took — thoughts, tool calls, results — on the
way to an answer. **Trajectory evals** grade the *path*, not just the destination.
See [Phase 4](../curriculum/phase-4-evals-and-regression/).

### Workflow
A system where *code* controls the sequence of steps (chaining, routing,
parallelization) and the model fills in fixed slots — predictable and debuggable.
Contrast with **agent**. Prefer it whenever the steps are knowable in advance. See
[Phase 0, Lesson 02](../curriculum/phase-0-mental-models/02-workflow-vs-agent.md).

---

➡️ Back to [reference/README.md](README.md) · or
[reference/the-stack.md](the-stack.md).
