"""Provider factory — choose the LLM provider from configuration.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
LAYER:  agent

WHY a factory?
    The rest of the app should ask for "an LLMProvider" without hardcoding which
    one. This single function maps the `LLM_PROVIDER` setting to a concrete
    implementation. Swapping providers is a config change, not a code change.
    JAVA NOTE: this is a classic factory method returning an interface type — the
    object equivalent of Spring picking a bean by profile.
"""

from __future__ import annotations

from pytegration.agent.mock_provider import MockProvider
from pytegration.agent.provider import LLMProvider
from pytegration.core.config import LLMProviderName, Settings


def build_provider(settings: Settings) -> LLMProvider:
    """Return the configured LLM provider.

    The return type is the `LLMProvider` Protocol, so callers depend only on the
    interface. Both branches return something that structurally satisfies it.
    """
    if settings.llm_provider is LLMProviderName.CLAUDE:
        # SYNTAX TIP: a LOCAL (function-scoped) import. We import the Claude
        #   provider only when it's actually selected, so the `anthropic` SDK is
        #   not required to run the app in mock/offline mode, and an import error
        #   surfaces only for users who opted into Claude.
        from pytegration.agent.claude_provider import ClaudeProvider

        return ClaudeProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )

    return MockProvider()
