"""Unit tests for application settings.

LESSON: Module 7 (Testing). See docs/07-testing.md

These tests prove the config layer fails fast and parses values correctly —
the kind of cheap, fast checks that catch misconfiguration before deployment.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pytegration.core.config import AppEnv, LLMProviderName, Settings


def test_defaults_are_offline_and_safe() -> None:
    """With no overrides, the app defaults to the offline mock provider."""
    settings = Settings()
    assert settings.llm_provider is LLMProviderName.MOCK
    assert settings.docs_enabled is True  # docs on outside production


def test_cors_origins_are_split_and_trimmed() -> None:
    """The comma-separated CORS string becomes a clean list."""
    settings = Settings(cors_origins="http://a.com, http://b.com ,")
    assert settings.cors_origins_list == ["http://a.com", "http://b.com"]


def test_docs_disabled_in_production() -> None:
    """SECURITY: interactive docs must be off in production."""
    settings = Settings(app_env=AppEnv.PRODUCTION)
    assert settings.docs_enabled is False


def test_claude_provider_requires_api_key() -> None:
    """Selecting the Claude provider without a key fails fast at startup.

    SYNTAX TIP: `pytest.raises(...)` asserts that the block raises the given
        exception — the analog of JUnit's `assertThrows`. The `match=` checks the
        error message, documenting the contract.
    """
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY is required"):
        Settings(llm_provider=LLMProviderName.CLAUDE, anthropic_api_key="")


def test_claude_provider_accepts_a_key() -> None:
    """With a key present, the Claude provider configuration is valid."""
    settings = Settings(llm_provider=LLMProviderName.CLAUDE, anthropic_api_key="sk-test")
    assert settings.anthropic_api_key == "sk-test"
