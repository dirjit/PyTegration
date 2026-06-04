# Module 7 — Testing

> **Goal:** write fast, isolated unit and integration tests with pytest — the
> JUnit of Python, but fixture-based.

## pytest vs JUnit

| pytest | JUnit |
|--------|-------|
| `def test_x():` (plain function) | `@Test void x()` |
| `assert a == b` (plain assert) | `assertEquals(a, b)` |
| **fixtures** (requested by parameter) | `@BeforeEach` + DI |
| `@pytest.mark.parametrize` | `@ParameterizedTest` |
| `pytest.raises(E)` | `assertThrows(E.class, ...)` |

pytest rewrites `assert` so failures show the actual values — no assertion library
needed.

## Fixtures: setup as composable dependencies

A **fixture** is a function that produces a test resource; a test receives it by
naming it as a parameter. Fixtures can depend on other fixtures. See
[`tests/conftest.py`](../tests/conftest.py) (auto-discovered):

```python
@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool, ...)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
```

The in-memory SQLite database is created fresh per test → fast and fully isolated,
yet it runs **real SQL** (these are "sociable" unit tests, not mock-the-DB tests).

## Two levels of test

- **Unit** ([`tests/unit/`](../tests/unit)): exercise one component — the service,
  the tools, config — against the in-memory DB. Fast and focused.
- **Integration** ([`tests/integration/`](../tests/integration)): drive the app
  over HTTP with an httpx `AsyncClient` + `ASGITransport` (in-process, no port).
  This is Spring's `MockMvc`/`WebTestClient`. It validates routing, validation,
  auth, error mapping, and serialization together:

```python
async def test_create_task_returns_201(client: AsyncClient):
    r = await client.post("/api/v1/tasks", json={"title": "Ship it", "priority": "high"})
    assert r.status_code == 201
```

## Mocking the LLM

Tests force `LLM_PROVIDER=mock`, so the agent endpoint runs the deterministic
`MockProvider`. No network, no key, no flakiness — see
[`tests/integration/test_agent_api.py`](../tests/integration/test_agent_api.py)
and the behavioral evals in [`tests/evals/`](../tests/evals).

## Run

```bash
make test            # everything, offline
pytest tests/unit -q # just unit tests
pytest -k agent      # tests matching "agent"
```

➡️ Next: [Module 8 — Security](08-security.md)
