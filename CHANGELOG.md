# Changelog

## 0.2.0: Cosmic Explorer

### Added
- **Cosmic Explorer** (`/explore`): an educational page for kids aged about 7–12
  that builds a mental map of the universe. It includes the Cosmic Zoom with a
  cosmic-address card, Worlds, the Light Time Machine, Space Gym, Scale Walk,
  the Moon phase with sky missions, a Quiz, Careers, and XP, ranks and badges
  kept in the browser.
- **Public, read-only API** at `/api/v1/cosmos/*` (atlas, objects, zoom,
  time-machine, weight, age, scale-model, travel, compare, moon, quiz, careers).
- **Nova, the Space Guide** (`POST /api/v1/agent/guide`, needs an API key): a
  kid-safe agent with read-only tools that ground every number in tested code.
- `agent/toolbox.py`: a generic `Toolbox[C]`. `run_agent` now takes
  `toolbox=` instead of `service=`.
- Lesson [Module 11](docs/11-cosmic-explorer.md) and a
  [guide for educators](docs/cosmic-explorer-for-educators.md).
- `.env.example` (the README already told you to copy it, but it was missing).

### Fixed (found while reviewing v0.1)
- **Async DB broke on Python ≥ 3.13**: SQLAlchemy only installs `greenlet`
  automatically on some platforms, so every database test failed with
  "the greenlet library is required". The dependency is now
  `sqlalchemy[asyncio]`.
- **`.env.example` was silently gitignored**: `.gitignore` had
  `!.env.example   # comment` on one line. Git has no inline comments, so the
  comment became part of the pattern and the exception never matched.
- **A tool error crashed the whole agent request**: a handler raising a domain
  error (for example, updating a missing task) escaped the loop and returned a
  404. `Toolbox.dispatch` now returns it to the model as a recoverable tool
  error.

### Changed
- `run_agent(..., service=...)` became `run_agent(..., toolbox=task_toolbox(service))`.
- Static files under `/explore/` don't count against the rate limit.
