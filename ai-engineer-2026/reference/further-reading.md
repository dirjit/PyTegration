# Further Reading

> **Goal:** a curated, phase-organized reading list — primary sources only, no
> filler. Read these *as you hit the matching phase*, not all at once.

Two ground rules, consistent with this curriculum's voice:

1. **Primary sources beat hot takes.** Provider docs, the original papers, and
   maintainer docs over thread summaries.
2. **No invented links.** Where a stable canonical URL exists, it's given. Where it
   doesn't (or might drift), the resource is *described* with enough detail to find
   it in one search — that's deliberate, not laziness. Treat any URL as
   verify-before-you-cite.

---

## Phase 0 — Mental models

- **Anthropic — "Building Effective Agents."** The canonical write-up on workflows
  vs. agents and the core patterns (prompt chaining, routing, parallelization,
  orchestrator-worker, evaluator-optimizer). Read it *first*.
  `https://www.anthropic.com/engineering/building-effective-agents`
- **"Lost in the Middle: How Language Models Use Long Contexts"** (Liu et al.).
  The paper behind **context rot** — models attend best to the start and end of a
  long context. Search the title; it's on arXiv and widely mirrored.
- **The Anthropic engineering blog.** Ongoing, high-signal posts on context
  engineering, agent design, and harness patterns. `https://www.anthropic.com/engineering`
- **A tokenizer playground** (any provider's). For the Lesson 01 exercise — paste
  text and watch words become **tokens**. Search "tokenizer playground."

➡️ Lessons:
[Phase 0](../curriculum/phase-0-mental-models/).

---

## Phase 1 — Your first agent (raw loop + Agent SDK)

- **Anthropic API docs — Messages, tool use, streaming.** The reference for the
  raw **agent loop** you'll hand-write: `tool_use` / `tool_result` blocks, the
  loop's stop conditions, streaming. Start at `https://docs.anthropic.com` (also
  reachable via `https://platform.claude.com/docs`).
- **Claude Agent SDK / Claude Code docs.** Your **reference harness** — study
  CLAUDE.md, Skills, sub-agents, hooks, filesystem-as-memory. Linked from the
  Anthropic docs above under the agent/Claude Code sections.
- **Model Context Protocol (MCP).** The open standard for wiring tools to models.
  `https://modelcontextprotocol.io`

➡️ Lessons:
[Phase 1](../curriculum/phase-1-first-agent/).

---

## Phase 2 — Production architecture (LangGraph + Deep Agents)

- **LangGraph documentation.** State machines, the checkpointer / **durable
  execution** (PostgresSaver), time-travel debugging, and persistence. The
  canonical docs are linked from `https://www.langchain.com` (LangGraph section).
- **LangChain documentation.** Background concepts the LangGraph docs assume.
  `https://www.langchain.com`
- **Deep Agents docs.** The packaged harness on LangGraph — planning middleware,
  virtual filesystem, sub-agent spawning, automatic context compression, skills.
  Find it via the LangChain org's repositories / docs (search "Deep Agents
  LangChain").

➡️ Lessons:
[Phase 2](../curriculum/phase-2-production-architecture/) · Stack rationale:
[reference/the-stack.md](the-stack.md).

---

## Phase 3 — Build the harness yourself

- **Anthropic — "Building Effective Agents"** (again, with new eyes). On a second
  read, after you've used a framework, you'll see exactly which primitives you're
  re-implementing.
- **The Claude Agent SDK / Claude Code source and docs**, read as a *reference
  implementation*. The goal of Phase 3 is to build your own ~1,500-line harness;
  reading a mature one shows you the shape to aim for.
- **Your own build log.** Not a link — a discipline. The README is explicit:
  architecture decisions, failures, and recoveries in `/your-notes/` *are* your
  interview material.

➡️ Lessons:
[Phase 3](../curriculum/phase-3-build-the-harness/).

---

## Phase 4 — Evals & regression

- **SWE-bench** — the paper and project site. What "real GitHub issue fixing"
  actually measures, and the Verified subset. Search "SWE-bench" for the official
  site (`swebench.com`) and the arXiv paper.
- **GAIA** — the paper, "GAIA: a benchmark for General AI Assistants." Search the
  title for the arXiv paper; the dataset is on the Hugging Face Hub.
- **τ-bench (tau-bench)** — the paper on tool-use customer-service agents. Search
  "tau-bench" for the paper and the reference implementation repo.
- **[reference/benchmarks.md](benchmarks.md)** — read this *before* the papers, so
  you read them with the `model × harness` lens and don't anchor on stale numbers.
- **Observability tool docs** for whichever one you picked: **LangSmith**
  (`https://www.langchain.com`, LangSmith section), **Braintrust**
  (`https://www.braintrust.dev`), or **Arize Phoenix** (`https://phoenix.arize.com`).

➡️ Lessons:
[Phase 4](../curriculum/phase-4-evals-and-regression/).

---

## Phase 5 — Production hardening

- **OWASP — "Top 10 for Large Language Model Applications" (LLM Top 10).** The
  canonical security checklist: **prompt injection**, insecure output handling,
  data leakage, and more. Find it on `https://owasp.org` (search "OWASP Top 10
  LLM").
- **Anthropic API docs — prompt caching, batch API, streaming.** The primary
  sources for the cost/latency levers in Phase 5: prefix-match caching rules, the
  **batch API** discount, and streaming for long outputs. Under
  `https://docs.anthropic.com`.
- **Your provider's status page and rate-limit docs.** Resilience starts with
  knowing your real limits and failure modes — read the rate-limit and error-code
  pages for whichever model API you ship on.

➡️ Lessons:
[Phase 5](../curriculum/phase-5-production-hardening/).

---

## Capstone projects

Each [project spec](../projects/) lists its own targeted reading. Cross-cutting
references:

- **Edge / on-device** — your mobile runtime's docs and quantization guides for
  the **SLM** in [Project 1](../projects/01-edge-slm-mobile-app.md).
- **Multimodal** — your model provider's vision/audio API docs for
  [Project 3](../projects/03-multimodal-video-agent.md).
- **Privacy-first** — OWASP LLM Top 10 (above) and your jurisdiction's data
  regulations for [Project 4](../projects/04-personal-life-os-agent.md).

---

> **A note on link rot.** Provider doc URLs reorganize and projects get renamed
> (see [the-stack.md](the-stack.md)'s warning). If a link 404s, search the
> resource's *name* — the names here are chosen to be stable even when the URLs
> aren't.

➡️ Back to [reference/README.md](README.md).
