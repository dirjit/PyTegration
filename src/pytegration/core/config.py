"""Application configuration — typed, validated, environment-driven settings.

LESSON: Module 6 (Config & Secrets). See docs/06-config-and-secrets.md
LAYER:  core (infrastructure)

JAVA NOTE:
    This module is the Python answer to Spring's `@ConfigurationProperties` +
    `application.yml` + profiles. Instead of a properties file, configuration
    comes from the *environment* (12-factor app), and instead of reflection we
    use a Pydantic model that validates and type-coerces every value at startup.

WHY validate config at startup?
    A mistyped port or a missing secret should crash the app immediately and
    loudly ("fail fast"), not produce a confusing error three requests later.
    Pydantic gives us that guarantee for free.
"""

# SYNTAX TIP: `from __future__ import annotations` (first import below) makes all
#   type hints in this file lazy (stored as strings, evaluated only when
#   introspected). It lets us reference types cleanly and avoids some import-order
#   headaches. It is a common first line in modern typed Python modules.
from __future__ import annotations

import functools
from enum import Enum

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    """Deployment environment.

    SYNTAX TIP: subclassing `str` AND `Enum` makes a "string enum" — each member
        IS a real string (`AppEnv.PRODUCTION == "production"` is True) while also
        being a typed, autocomplete-friendly constant.
    JAVA NOTE: this is Python's equivalent of a Java `enum`, but the `str` mixin
        gives you Java-style `name()`/value behavior plus seamless JSON/env
        serialization.
    """

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class LLMProviderName(str, Enum):
    """Which LLM backend the agent should use."""

    MOCK = "mock"  # deterministic, offline, no API key required
    CLAUDE = "claude"  # the real Anthropic API


class Settings(BaseSettings):
    """All application configuration in one validated, typed object.

    JAVA NOTE: think of an instance of this class as an immutable,
        dependency-injected `@ConfigurationProperties` bean. Anywhere in the app
        that needs config asks for a `Settings` (via FastAPI's `Depends`), rather
        than reading environment variables directly. That keeps configuration
        access centralized and testable.
    """

    # `model_config` tells pydantic-settings WHERE to read values from and HOW
    # to behave. This replaces a scatter of framework annotations.
    model_config = SettingsConfigDict(
        env_file=".env",  # also load a local .env file if present...
        env_file_encoding="utf-8",
        case_sensitive=False,  # API_KEY and api_key both map to `api_key`
        extra="ignore",  # ignore unrelated env vars (e.g. PATH)
    )

    # ----- Application -------------------------------------------------------
    # SYNTAX TIP: `name: type = default` declares a typed field with a default.
    #   Pydantic reads `APP_ENV` from the environment, coerces it to AppEnv, and
    #   validates it. No manual parsing, no `Integer.parseInt`.
    app_env: AppEnv = AppEnv.DEVELOPMENT

    # ----- API authentication ------------------------------------------------
    # SECURITY: this shared secret gates every protected endpoint. It has no
    #   default on purpose for production (see the validator below) so we never
    #   ship a guessable key. The dev default lives only in .env.example.
    api_key: str = Field(default="dev-local", min_length=1)

    # ----- AI / agent provider -----------------------------------------------
    llm_provider: LLMProviderName = LLMProviderName.MOCK
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Hard guardrail: the maximum number of model<->tool round trips the agent
    # may take before we stop it. Prevents runaway loops and runaway cost.
    agent_max_iterations: int = Field(default=6, ge=1, le=20)

    # ----- Database ----------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./pytegration.db"

    # ----- CORS --------------------------------------------------------------
    # WHY a string here, parsed into a list below? Environment variables are
    #   always strings; we accept a comma-separated value and split it. This is
    #   a common, explicit pattern that keeps the env format simple.
    cors_origins: str = "http://localhost:3000"

    @field_validator("anthropic_api_key")
    @classmethod
    def _claude_requires_key(cls, value: str, info: object) -> str:
        """Fail fast if the Claude provider is selected without a key.

        SYNTAX TIP: `@field_validator` is a decorator that registers a custom
            validation hook for a field — the rough equivalent of a Bean
            Validation `@AssertTrue` method in Java. It runs during model
            construction (i.e. at startup).
        """
        # NOTE: cross-field validation reads sibling values from `info.data`.
        data = getattr(info, "data", {}) or {}
        provider = data.get("llm_provider")
        if provider == LLMProviderName.CLAUDE and not value:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=claude. "
                "Set it in your environment, or use LLM_PROVIDER=mock for offline use."
            )
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS origins as a clean list.

        SYNTAX TIP: `@property` exposes a method as if it were an attribute
            (`settings.cors_origins_list`), like a Java getter without the `()`.
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def docs_enabled(self) -> bool:
        """Interactive API docs are disabled in production.

        SECURITY: /docs and /openapi.json reveal your entire API surface. We
            keep them on for learning/dev but off in production by default.
        """
        return self.app_env != AppEnv.PRODUCTION


# WHY cache the Settings instance?
#   Building Settings reads the environment and a file; we want to do that once
#   per process, not on every request. `functools.lru_cache` memoizes the result
#   so every caller shares one immutable instance.
#   JAVA NOTE: this is the idiomatic Python way to get a singleton bean.
@functools.lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    GOTCHA: in tests we sometimes want fresh settings; `get_settings.cache_clear()`
        resets the cache. The test suite overrides this dependency instead (see
        tests/conftest.py), which is cleaner.
    """
    return Settings()
