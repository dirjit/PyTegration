# Module 2 — Async & Await

> **Goal:** understand Python's concurrency model and why this whole project is
> `async`.

## The one-paragraph model

Python runs your async code on a single-threaded **event loop**. When a coroutine
`await`s something I/O-bound (a database query, an HTTP call), it *yields* control
back to the loop, which runs other coroutines until the I/O completes. One thread,
many in-flight requests — no thread-per-request pool.

```python
async def get_task(task_id: int) -> TaskRead:   # a coroutine
    task = await self._repo.get(task_id)         # yield while the DB works
    ...
```

## Java analogies (and where they break)

| Python | Closest Java |
|--------|--------------|
| `async def` function (coroutine) | a method returning `CompletableFuture` |
| `await x` | `.get()` / `.join()`, but **non-blocking** |
| the event loop | the reactor in Project Reactor / Netty |
| `asyncio.gather(...)` | `CompletableFuture.allOf(...)` |

**The big difference — the GIL.** CPython has a Global Interpreter Lock, so only
one thread runs Python bytecode at a time. Async is therefore about **I/O
concurrency**, not CPU parallelism. For CPU-bound work you use multiple processes,
not threads. (Java's threads give true parallelism; Python's async does not.)

## Rules of the road

1. You can only `await` inside an `async def`.
2. **Never** call a blocking function (e.g. `time.sleep`, a sync DB driver) inside
   a coroutine — it freezes the *entire* event loop. Use async equivalents
   (`asyncio.sleep`, `aiosqlite`/async SQLAlchemy). This is why we use the async
   engine in [`db/session.py`](../src/pytegration/db/session.py).
3. `async with` is the async form of try/finally resource management; `async for`
   iterates an async generator. We use both for sessions and dependencies.

## Where it shows up here

- Every route handler, service method, and repository method is `async`.
- The DB session dependency is an **async generator** (`async with ... yield`) —
  see [`db/session.py`](../src/pytegration/db/session.py).
- The app lifespan (`@asynccontextmanager`) creates/disposes the engine around the
  server's lifetime — see [`main.py`](../src/pytegration/main.py).
- Tests are `async def` too, run by `pytest-asyncio`.

➡️ Next: [Module 3 — API Design with FastAPI](03-api-design-fastapi.md)
