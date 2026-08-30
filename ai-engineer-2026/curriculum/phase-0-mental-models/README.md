# Phase 0 — Build Correct Mental Models · Weeks 1–2

> **Goal:** install the mental models *before* you write a line of agent code, so
> that when something breaks at 2am you can reason about it instead of
> guess-and-check.

Most beginners skip this phase. They dive into tutorials, copy an agent loop they
don't understand, and then freeze the first time it loops forever or hallucinates
a tool call. The engineers who get hired did the opposite: they spent two weeks
making sure the words *harness*, *agent*, *context*, and *eval* meant something
precise.

This phase is **reading and writing, not coding.** You will write code soon
enough. First, get the map.

## Lessons

| # | Lesson | The idea you'll own |
|---|--------|---------------------|
| 00 | [What an AI Engineer actually does](00-what-an-ai-engineer-does.md) | The job is the harness, not the prompt |
| 01 | [How LLMs behave (a math-free model)](01-how-llms-behave.md) | Why models hallucinate, drift, and aren't deterministic |
| 02 | [Workflow vs. Agent](02-workflow-vs-agent.md) | When to use a fixed control flow vs. a loop |
| 03 | [The 5 workflow patterns](03-five-workflow-patterns.md) | Chaining, routing, parallelization, orchestrator-worker, evaluator-optimizer |
| 04 | [The harness & the 4 context primitives](04-harness-and-context-primitives.md) | Write / Select / Compress / Isolate |

## What you ship

A **2-page document, in your own words**, that defines:

1. Workflow vs. agent (and how you'd decide between them for a real task)
2. The 5 workflow patterns
3. The 4 context primitives
4. The orchestrator-worker pattern

See **[project.md](project.md)** for the exact rubric. If you can't write it
without looking anything up, you haven't read carefully enough — go back. This
doc is the cheapest, highest-leverage artifact in the whole course: it forces you
to *compress* the concepts, which is the same skill you'll later teach an agent.

➡️ Start: [Lesson 00 — What an AI Engineer actually does](00-what-an-ai-engineer-does.md)
