# Authoring style guide (internal)

The contract every lesson in this curriculum follows. Keep the voice consistent.

## Voice
- Direct, second-person, build-first. Confident but never hype-for-hype's-sake.
- Respect the reader's time. Lead with the mental model, then the mechanics.
- Honest about trade-offs and uncertainty. Flag speculative claims explicitly.

## Required structure for a lesson file
1. `# Lesson N — Title`
2. `> **Goal:** …` one-line blockquote.
3. **The mental model** — the core idea before any code.
4. At least one **diagram** (Mermaid preferred; ASCII where clearer).
5. **Runnable or near-runnable code** for any concept that can be code.
6. **A war story / anecdote** callout that makes the concept stick.
7. **Pitfalls** — the specific ways this bites people in production.
8. **Exercises** — 2–4, concrete.
9. **Exit check** — what "you've got it" looks like.
10. `➡️ Next:` link.

## Callout tags (bold inline, greppable)
- `**WHY:**` design rationale.
- `**GOTCHA:**` a footgun.
- `**SECURITY:**` a safety-relevant choice.
- `**WAR STORY:**` a concrete anecdote.
- `**COST:**` a money/latency implication.

## Diagrams
- Use Mermaid (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `gantt`).
- Keep node labels short; put detail in prose.

## Code
- Python 3.11+, type-hinted. Prefer `async` for agent code.
- Provider-agnostic where possible; when concrete, default to the Claude/Anthropic
  SDK and say so. Always show the loop, never hide it behind magic.
- Mark anything that needs an API key; offer an offline/mock path where feasible.

## Accuracy guardrails
- Do not invent benchmark numbers. Point to `reference/benchmarks.md`.
- Frameworks churn — teach the primitive, name the framework as the current vehicle.
