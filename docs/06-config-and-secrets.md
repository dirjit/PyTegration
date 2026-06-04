# Module 6 — Config & Secrets

> **Goal:** load configuration from the environment, validate it at startup, and
> keep secrets out of source control.

## 12-factor config

A [12-factor app](https://12factor.net/config) reads configuration from the
**environment**, not from checked-in files. This lets the same image run in dev,
staging, and prod with different env vars — and keeps secrets out of git.

See [`core/config.py`](../src/pytegration/core/config.py). `pydantic-settings`
gives us a typed, validated settings object:

```python
class Settings(BaseSettings):
    api_key: str = Field(default="dev-local", min_length=1)
    llm_provider: LLMProviderName = LLMProviderName.MOCK
    agent_max_iterations: int = Field(default=6, ge=1, le=20)
```

| Python | Spring |
|--------|--------|
| `BaseSettings` | `@ConfigurationProperties` |
| env vars / `.env` | `application.yml` + env overrides |
| `@field_validator` | Bean Validation (`@AssertTrue`) |
| `AppEnv` enum | Spring profiles |

## Fail fast

Config is validated **at startup**. A bad value crashes the process immediately
with a clear message, instead of failing mysteriously on request #1000. Example:
selecting the Claude provider without a key is rejected by a validator:

```python
@field_validator("anthropic_api_key")
def _claude_requires_key(cls, value, info):
    if info.data.get("llm_provider") == LLMProviderName.CLAUDE and not value:
        raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=claude.")
```

## Secrets hygiene

- **`.env` is gitignored**; **`.env.example`** (committed) documents the variables
  with safe placeholders. Copy one to the other to get started.
- Secrets are read from the environment only — never hardcoded, never logged. The
  logging layer even redacts secret-looking fields (Module 9).
- In Docker, `.dockerignore` keeps `.env` out of the image.

**PRODUCTION UPGRADE:** inject secrets from a manager (AWS Secrets Manager, Vault,
Kubernetes secrets) rather than a `.env` file.

## How it's consumed

Settings are built once (cached `get_settings()`), stored on `app.state`, and
injected via a dependency (`SettingsDep`) — so nothing reads `os.environ`
scattered around the code, and tests can pass a custom `Settings` to
`create_app(settings=...)`.

➡️ Next: [Module 7 — Testing](07-testing.md)
