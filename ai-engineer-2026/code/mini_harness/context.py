"""context.py — Harness component #3: context assembly + compaction.

> Prompt engineering is now a *sub-skill* of context engineering: curating every
> token in the window at every step. This module owns that budget.

It does two jobs that map directly onto two of the four context primitives:
  - WRITE/assembly: build the system prompt + message list the model sees.
  - COMPRESS:      when the window approaches a threshold (a common trigger is
                   ~85% full), replace old history with a shorter summary.

Assembly is WORKING. Compaction is a clearly-marked TODO — it's the heart of
Phase 3 and the source of the Lesson-04 war story (a bad compaction that dropped
the user's constraints made the agent "forget"; the fix was *better compaction*,
not a better model).

Token counting here is a crude estimate (chars/4) so the file runs offline. COST:
in production, count tokens with the provider's tokenizer/endpoint — never
`tiktoken` against a non-OpenAI model, and never a blind multiplier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# A rough offline token estimate. Real harnesses call the provider's token-count
# endpoint. ~4 chars/token is a serviceable stand-in for the threshold math.
CHARS_PER_TOKEN = 4


def estimate_tokens(messages: list[dict[str, Any]], system: str = "") -> int:
    """Crude token estimate for threshold checks. Replace with a real tokenizer."""
    total_chars = len(system)
    for msg in messages:
        content = msg.get("content", "")
        total_chars += len(content) if isinstance(content, str) else len(str(content))
    return total_chars // CHARS_PER_TOKEN


@dataclass
class ContextManager:
    """Assembles the prompt and decides when to compact.

    `window_tokens` is the model's context window; `compact_at` is the fraction
    (0–1) at which compaction triggers — 0.85 by default per Lesson 04.
    `pinned` holds durable facts/constraints that MUST survive every compaction
    (the war-story fix: pin "must cite sources", "budget $1", etc.).
    """

    system_prompt: str
    window_tokens: int = 200_000
    compact_at: float = 0.85
    pinned: list[str] = field(default_factory=list)
    # Pluggable summarizer: (messages_to_compress) -> summary_text.
    # Defaults to a no-op placeholder; the student wires in a real model call.
    summarizer: Callable[[list[dict[str, Any]]], str] | None = None

    def assemble_system(self) -> str:
        """Build the full system prompt: base prompt + pinned durable context.

        Pinned items are appended so they're always in front of the model — this
        is the WRITE primitive applied to constraints (keep them present even
        after history is compressed away).
        """
        if not self.pinned:
            return self.system_prompt
        pins = "\n".join(f"- {p}" for p in self.pinned)
        return f"{self.system_prompt}\n\n## Durable context (do not forget)\n{pins}"

    def should_compact(self, messages: list[dict[str, Any]]) -> bool:
        """True when estimated usage crosses the compaction threshold."""
        used = estimate_tokens(messages, self.assemble_system())
        return used >= int(self.window_tokens * self.compact_at)

    def compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace old history with a summary, keeping recent turns verbatim."""
        # TODO(student): implement real compaction. The shape to aim for:
        #   1. Keep the last K turns verbatim (recency matters most).
        #   2. Summarize everything older into a single "story so far" message
        #      using `self.summarizer` (a cheap model call — ISOLATE-friendly).
        #   3. NEVER drop pinned constraints (they live in the system prompt, so
        #      assemble_system handles that — but double-check your summary too).
        #   4. Return the new, shorter message list.
        #
        # GOTCHA (Lesson 04 war story): compression is lossy. Summarize durable
        # facts and DECISIONS, not chatter. Dropping the user's constraints during
        # compaction is the #1 cause of an agent "forgetting" on long tasks.
        #
        # The placeholder below is intentionally a near-NO-OP so the skeleton
        # runs; replace it with a real summarizing implementation.
        keep_recent = 4
        if self.summarizer is None or len(messages) <= keep_recent:
            return messages  # nothing to do yet (placeholder behavior)

        old, recent = messages[:-keep_recent], messages[-keep_recent:]
        summary_text = self.summarizer(old)
        summary_msg = {
            "role": "user",
            "content": f"[story so far — compacted]\n{summary_text}",
        }
        return [summary_msg, *recent]

    def maybe_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compact iff over threshold. The loop calls this each iteration."""
        if self.should_compact(messages):
            return self.compact(messages)
        return messages
