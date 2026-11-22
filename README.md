# PyTegration

> A production-grade **FastAPI Task Manager + Claude AI agent**, built as a guided
> course for developers who know **Java** and want to master **Python for API,
> application, and agentic (LLM) integration**.

PyTegration is two things at once:

1. **A real, runnable starter project** — clean layered architecture, tests,
   security, migrations, Docker, and CI. Fork it and build on it.
2. **A course** — the code is densely commented with `JAVA NOTE`, `SYNTAX TIP`,
   `WHY`, `SECURITY`, and `GOTCHA` callouts, and the [`docs/`](docs/) folder
   contains an ordered set of lessons.

---

## What you'll build

A **Task Manager** REST API (create / list / update / triage tasks) plus an
**AI assistant** endpoint. The assistant is a Claude-powered agent that uses
*tool calling* to operate on the very same task API — so you learn how an agent
safely drives your own application.

The whole thing runs **offline with no API key** thanks to a deterministic mock
LLM provider, so you can study every concept (including the agent) without
signing up for anything.

### New in v0.2: 🚀 Cosmic Explorer, a universe map for kids

The same architecture now also serves a page for **children aged about 7–12**
at **`/explore`**. It aims to build a *mental map of the universe* and get
them interested in space science:

- 🔭 **Cosmic Zoom**: zoom out from Earth to the observable universe while
  filling in your *cosmic address*.
- 🪐 **Worlds**: 23 planets, moons, stars, galaxies and spacecraft, with
  trip-time and size calculators.
- ⏳ **Light Time Machine**: "the light from Andromeda set off before the first
  modern humans lived".
- ⚖️ **Space Gym**: your weight, jump height and age on other worlds.
- 📏 **Scale Walk**: a beach-ball Sun and a peppercorn Earth 32 m away.
- 🌙 **Tonight**: the Moon phase for today plus real sky missions.
- 🧠 **Quiz**, 👩‍🚀 **Careers**, and 🤖 **Nova**, an AI space guide whose
  numbers all come from tested code.
- XP, ranks and badges, stored only in the child's browser.

For developers it's [Module 11](docs/11-cosmic-explorer.md): a second domain,
a public read-only API, a static page with a strict CSP, and a generic
`Toolbox[C]` so one agent loop runs two agents. For parents and teachers
there's a [classroom guide](docs/cosmic-explorer-for-educators.md).

---

## Quick start

```bash
# 1. Create an isolated environment and install everything (see Module 0).
make setup

# 2. Configure local settings (safe placeholder values are fine).
cp .env.example .env

# 3. Create the database schema.
make migrate

# 4. Run the API (interactive docs at http://localhost:8000/docs).
make run

# 5. Open the kids' Cosmic Explorer at http://localhost:8000/explore
```

Then, in another terminal:

```bash
# Create a task (the X-API-Key header value comes from your .env).
curl -s -X POST localhost:8000/api/v1/tasks \
  -H 'X-API-Key: dev-local' -H 'Content-Type: application/json' \
  -d '{"title":"Write tests","priority":"high"}'

# Ask the AI assistant (works offline with the mock provider):
curl -s -X POST localhost:8000/api/v1/agent/chat \
  -H 'X-API-Key: dev-local' -H 'Content-Type: application/json' \
  -d '{"message":"Create a high priority deploy task, then summarize my open tasks"}'
```

Run the quality gate (lint + type-check + tests) exactly like CI does:

```bash
make all
```

---

## The course

Read the code alongside these lessons. Each maps to real files in the project
and calls out the **Java analog** for every new concept.

| # | Lesson | Concepts |
|---|--------|----------|
| 0 | [Setup & Tooling](docs/00-setup.md) | venv & pip vs Maven, `pyproject.toml` ≈ `pom.xml`, editable install, lockfiles |
| 1 | [Python for Java Devs](docs/01-python-for-java-devs.md) | modules/imports, type hints + mypy, dataclass vs Pydantic vs ORM model, enums, `None`/truthiness |
| 2 | [Async & Await](docs/02-async-await.md) | event loop, coroutines, `await`, `async with`; vs threads/`CompletableFuture`/the GIL |
| 3 | [API Design with FastAPI](docs/03-api-design-fastapi.md) | routers, Pydantic request/response, status codes, OpenAPI, `Depends` DI |
| 4 | [Layered Architecture](docs/04-layered-architecture.md) | api → service → repository → db; DTO vs entity; dependency direction |
| 5 | [Persistence](docs/05-persistence-sqlalchemy.md) | SQLAlchemy 2.0 `Mapped[]`, async sessions, transactions, Alembic migrations |
| 6 | [Config & Secrets](docs/06-config-and-secrets.md) | pydantic-settings, 12-factor, fail-fast validation, secret hygiene |
| 7 | [Testing](docs/07-testing.md) | pytest fixtures vs JUnit, async tests, httpx client, mocking the LLM |
| 8 | [Security](docs/08-security.md) | API-key auth, authz, validation, rate limiting, dependency pinning |
| 9 | [Observability](docs/09-observability.md) | structured logging, request IDs, centralized error handling |
| 10 | [Agentic / LLM Integration](docs/10-agentic-llm.md) | `Protocol` interfaces, tool use, the agent loop, prompt caching, guardrails, evals |
| 11 | [Cosmic Explorer (v0.2)](docs/11-cosmic-explorer.md) | DB-less repository, pure-function services, public vs protected routers, static files + CSP, `Generic[T]` toolbox, LLM safety for kids |

---

## How to read the code

Every source file opens with a docstring naming its **lesson** and **layer**.
Inside the code, look for these greppable tags (each explains one idea, on its
first occurrence):

- `# SYNTAX TIP:` — a Python language feature, explained where it first appears.
- `# JAVA NOTE:` — a direct Java → Python comparison.
- `# WHY:` — the design rationale behind a decision.
- `# SECURITY:` — a security-relevant choice.
- `# GOTCHA:` — a Python footgun that surprises Java developers.

Try: `grep -rn "JAVA NOTE" src/` to take a tour of the comparisons.

---

## Project layout

```
src/pytegration/
  main.py        # app factory + wiring (the composition root)
  core/          # cross-cutting infra: config, logging, security, errors, middleware
  db/            # SQLAlchemy engine, session, ORM models
  domain/        # framework-free domain types (enums, entities)
  schemas/       # Pydantic request/response DTOs (the API contract)
  repositories/  # data access (CRUD over the DB session)
  services/      # business logic (orchestrates repositories)
  api/           # FastAPI routers + dependency-injection wiring
  agent/         # LLM provider abstraction, toolboxes, and the agent loop
  web/           # the Cosmic Explorer page (HTML/CSS/JS, no build step)
tests/           # unit, integration, and agent eval tests
docs/            # the long-form lessons linked above
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

---

## License

MIT — use it, fork it, teach with it.
