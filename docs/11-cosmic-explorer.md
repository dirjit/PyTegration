# Module 11 — Cosmic Explorer (v0.2)

> **Goal:** add a second, very different product to the same codebase (a kids'
> universe explorer) and see how the architecture from Modules 3–10 absorbs it:
> a new domain, a public read-only API, a static web page, and a second AI agent
> that shares the first agent's loop.

v0.1 taught the stack through a Task Manager. v0.2 asks a harder question: *can
the same layers carry a product with a different audience, risk profile and
data shape?* The new feature is the **Cosmic Explorer**, a page for children aged
about 7–12 at [`/explore`](http://localhost:8000/explore). It aims to:

1. **Build a mental map of the universe**: where we are (the *cosmic address*),
   how big things are, and how far away they are.
2. **Make huge numbers feel real**: peppercorn planets 32 m from a beach-ball Sun,
   or a car trip to the Moon that would take 160 days.
3. **Show that looking far means looking back in time**: the *Light Time
   Machine*.
4. **Spark interest in the field**: real careers, things to try tonight, and a
   space guide that answers questions.

## What was added, layer by layer

```
domain/cosmos.py               frozen dataclasses: CelestialObject, ZoomLevel, Milestone, …
repositories/cosmos_data.py    the curated, reviewed data set (Python constants)
repositories/cosmos_catalog.py CosmosCatalog: an in-memory, read-only repository
services/cosmos_service.py     all the maths + kid-friendly wording (pure functions)
schemas/cosmos.py              response DTOs (labels added, quiz answers hidden)
api/routes/cosmos.py           PUBLIC /api/v1/cosmos/* endpoints
agent/toolbox.py               generic Toolbox[C] extracted from v0.1's tools.py
agent/guide_tools.py           Nova's read-only, grounding tools
web/                           index.html + app.js + styles.css (no build step)
```

The dependency direction is unchanged: `api → service → repository → domain`.
The agent layer calls the same `CosmosService` as the REST routes. That's the
v0.1 rule that the agent gets the same authority as the API, applied to a new domain.

## 1. A repository without a database

`CosmosCatalog` has no SQLAlchemy in it. It indexes Python constants once and
answers `find("north star")`, `list_objects(kind=…)` and so on. The **repository
pattern is about the interface**, not the storage. If the atlas ever needs
editing by teachers, only `cosmos_data.py` gets swapped for a DB-backed source.

> **JAVA NOTE:** a `@Repository` backed by an immutable `Map`. The catalog is
> built once per process (see `api/deps.py`), so it's a singleton-scoped bean,
> while `TaskService` is request-scoped because it holds a DB session.

Why Python constants instead of JSON? **mypy type-checks them.** A typo'd field
name fails the build, and a fact correction is an ordinary reviewed diff.

## 2. Pure functions are the easiest code to trust

`CosmosService` does no I/O. Every calculation (weight × gravity, light-travel
time, scale model, moon phase) is a pure function of its inputs, so
[`tests/unit/test_cosmos_service.py`](../tests/unit/test_cosmos_service.py) reads
like a list of facts:

```python
def test_drive_to_the_moon_takes_about_160_days(cosmos):
    legs = {leg.mode: leg for leg in cosmos.travel(cosmos.get_object("moon"))}
    assert legs["car on a highway"].label == "160 days"
```

**In an educational product a wrong number is a bug that teaches something
false**, so the data set gets tests too: every quiz answer is one of its
choices, zoom levels strictly grow, no two objects share an alias, and the
"all the planets fit between Earth and the Moon" claim is checked against the
catalog's own numbers.

**Inject the clock.** The Moon phase depends on "today". `CosmosService` takes an
optional `today`, and the integration tests override the `get_cosmos_service`
dependency to pin it. Without an injectable clock, a date-dependent test is a
flaky test.

## 3. Public vs protected: decide per route

| Endpoint | Auth? | Why |
|---|---|---|
| `GET /api/v1/cosmos/*` | **No** | Curated, read-only reference data. No user data, no writes, no LLM cost. |
| `POST /api/v1/agent/guide` | **API key** | Calls an LLM: real money, and free-text output. |
| `/explore/*` static files | No, and exempt from rate limiting | Cheap static files; a page load fetches several at once. |

The public routes live on a **separate router** (`public_v1_router` in
`api/router.py`), so you can't accidentally drop a protected route onto it.
Public doesn't mean unguarded: requests are still rate-limited per IP, and
every parameter is bounded (`earth_weight` must be in `(0, 500]`, names are at
most 60 characters, and so on). A test proves the old routes are still
protected (`test_protected_routes_stay_protected`).

The quiz shows a small version of a common rule: **never send the secret to the
client.** `QuizQuestionOut` has no `answer` field. The browser POSTs a choice and
the server checks it.

## 4. Serving a web page from FastAPI

```python
app.mount("/explore", SecureStaticFiles(directory=WEB_DIR, html=True), name="explore")
```

- **`package-data`** in `pyproject.toml` ships the HTML, CSS and JS inside the
  wheel. Without it, `pip install .` (used by the Dockerfile) would leave the
  page out. *JAVA NOTE:* this is `src/main/resources`.
- **`SecureStaticFiles`** adds a strict **Content-Security-Policy**
  (`default-src 'self'`). A children's page should load nothing from third
  parties: no trackers, CDNs or fonts. That's why the HTML has no inline
  scripts or `style=""` attributes.
- **`textContent`, never `innerHTML`.** Nova's replies come from an LLM. The page
  builds every node with a tiny `h()` helper that sets text, so model output can
  never become live HTML (no XSS).
- **Privacy by design.** XP, badges and the name on the address card live in the
  browser's `localStorage`. The Explorer Pass (API key) is kept in
  `sessionStorage`, which is forgotten when the tab closes. The server never
  receives anything personal.

## 5. One agent loop, two agents: the `Toolbox[C]` refactor

v0.1's loop called `dispatch_tool_call(service=TaskService…)` directly. To add
Nova without copying that code, the validate-and-dispatch logic moved to a
**generic** class:

```python
ContextT = TypeVar("ContextT")

class Toolbox(Generic[ContextT]):            # JAVA NOTE: class Toolbox<C>
    def __init__(self, context: ContextT, tools: Mapping[str, Tool[ContextT]]): ...
    def specs(self) -> list[ToolSpec]: ...
    async def dispatch(self, *, call_id, name, arguments) -> ToolResult: ...
```

`run_agent(provider=…, toolbox=…, …)` now depends on a two-method `ToolRunner`
**Protocol**, so the loop doesn't know which agent it is running. The task
assistant is `task_toolbox(service)` and Nova is `guide_toolbox(cosmos)`. **The
only differences between the two agents are the toolbox and the system
prompt.**

The refactor also **fixed a v0.1 bug**. If a tool handler raised a domain error
(for example, `update_task_status` on a task id that doesn't exist), the
`NotFoundError` escaped the loop and the whole chat request returned 404. Now
`Toolbox.dispatch` turns any `AppError` into an `is_error` tool result the model
can recover from. Unexpected exceptions still propagate, because a bug should
be loud.

## 6. Designing an LLM feature for children

[`GUIDE_SYSTEM_PROMPT`](../src/pytegration/agent/prompts.py) is mostly rules:
reading level, honesty about uncertainty, no personal details, and staying on
topic. But **prompts are soft guardrails**. The hard ones are in code:

| Risk | Hard guardrail |
|---|---|
| Model states a wrong number | **Grounding:** every number comes from a tool that runs tested code over reviewed data |
| Prompt injection does damage | All of Nova's tools are **read-only**, so there's nothing harmful to trigger |
| Long, costly, or abusive prompts | `GuideRequest.message` capped at 500 chars, iteration cap, API key, rate limit |
| LLM output rendered as HTML | `textContent` only, plus a CSP |
| Collecting children's data | Nothing personal is sent or stored server-side |

The offline `MockProvider` now has a second script. It picks which agent to
play from **which tools it is offered**, and finds object names in a question
using `CosmosCatalog.find_mentions` (whole words only, so "Sunday" doesn't
match "Sun"). The [evals](../tests/evals/test_agent_evals.py) check that each
kind of question goes to its *grounding* tool and that the tool's fact appears
in the reply.

## Try it

```bash
make run            # then open http://localhost:8000/explore
curl -s 'localhost:8000/api/v1/cosmos/time-machine?light_years=2537000' | python -m json.tool
curl -s -X POST localhost:8000/api/v1/agent/guide -H 'X-API-Key: dev-local' \
  -H 'Content-Type: application/json' -d '{"message":"Is Jupiter bigger than Earth?"}'
```

## Exercises

1. **Add a world.** Put Europa or Titan into `cosmos_data.py`. Which tests tell
   you if you forgot an alias or reused one?
2. **A new zoom level.** Add "the Local Interstellar Cloud" between the Solar
   System and the neighbourhood. What does `test_zoom_levels_get_strictly_bigger`
   protect you from?
3. **A new Nova tool.** Add `moon_phase_tonight` to `GUIDE_TOOLS`, teach the mock
   to route "what does the Moon look like tonight?" to it, and write an eval.
4. **Swap the source.** Load the quiz from a JSON file while keeping
   `CosmosCatalog`'s interface. Which layers change? (Only one should.)
5. **Harder:** the rate limiter keys anonymous users by IP, and a whole school
   often shares one IP. Design a fairer scheme for a classroom.
