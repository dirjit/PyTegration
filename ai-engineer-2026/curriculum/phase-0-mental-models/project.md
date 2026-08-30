# Phase 0 Project — The 2-Page Concepts Doc

> **Ship this before Phase 1.** No code. The deliverable is a 2-page document, in
> *your own words*, that proves the mental models are now *yours*.

## Why this is the project

Writing is compression, and compression is the core AI-engineering skill (it's
literally context primitive ③). If you can compress these concepts into two clear
pages from memory, you understand them. If you can't, you've been reading
passively. This doc costs an afternoon and saves you weeks of building things you
can't reason about.

## The brief

Write a **2-page** doc (≈800–1,000 words) titled *"Mental Models for AI
Engineering."* It must define, **in your own words, without looking**:

1. **Workflow vs. agent** — the difference, *and* a decision rule, *and* one
   example of each from your own domain.
2. **The 5 workflow patterns** — name each and give a one-line use case:
   prompt chaining, routing, parallelization, orchestrator-worker,
   evaluator-optimizer.
3. **The 4 context primitives** — Write, Select, Compress, Isolate — each with an
   example and the problem it solves.
4. **The orchestrator-worker pattern** — explain it in depth (it's the backbone of
   multi-agent systems) and how it uses the Isolate primitive.

## Rules

- **Closed book.** Write it, *then* check against the lessons and correct mistakes
  in a different color. The corrections are where the learning is.
- **Your words, your examples.** Examples copied from the lessons don't count; pull
  them from a domain you actually know.
- **Include at least one diagram you drew** (paper photo is fine).

## Self-grading rubric

Score yourself /12. Below 10 → re-read the relevant lesson and rewrite.

| Criterion | 0 | 1 | 2 |
|-----------|---|---|---|
| Workflow vs. agent | Can't distinguish | Distinguishes them | + decision rule + own examples |
| 5 patterns | Misses ≥2 | Names all 5 | + correct use case each |
| 4 primitives | Misses ≥1 | Names all 4 | + example + problem solved each |
| Orchestrator-worker | Vague | Explained | + ties to Isolate primitive |
| Clarity | Jargon soup | Readable | A peer could learn from it |
| Honesty | Hand-waves gaps | Notes uncertainties | Explicitly flags what's still fuzzy |

## Stretch (optional, recommended)

- Add a one-paragraph "what I'd build" sketch: pick a task, decide workflow vs.
  agent, name the patterns and primitives you'd use. This becomes the seed of your
  capstone choice.
- Publish it (blog/Gist) and link it. "Build in public" starts here — a clear
  concepts doc is genuine interview signal.

## Exit criteria for Phase 0

- [ ] Doc written closed-book, then corrected against the lessons.
- [ ] Self-graded ≥ 10/12.
- [ ] You can deliver the four definitions out loud, from memory, to a friend.

➡️ When this passes, start
[Phase 1 — Build Your First Agent From Scratch](../phase-1-first-agent/).
