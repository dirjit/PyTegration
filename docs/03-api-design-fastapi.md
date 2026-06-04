# Module 3 — API Design with FastAPI

> **Goal:** build typed, validated, self-documenting HTTP endpoints — the Spring
> MVC of the Python world.

## FastAPI ≈ Spring MVC, but type-driven

| FastAPI | Spring |
|---------|--------|
| `APIRouter` | `@RestController` + `@RequestMapping` |
| `@router.post("/tasks")` | `@PostMapping("/tasks")` |
| `payload: TaskCreate` (Pydantic) | `@RequestBody @Valid TaskCreate` |
| `Depends(...)` | `@Autowired` (but per-request, explicit) |
| auto `/docs` (OpenAPI) | Springdoc / Swagger UI |

FastAPI reads your **type hints** to validate input, serialize output, and
generate OpenAPI docs. The types aren't decoration — they *are* the contract.

## Anatomy of a route

See [`api/routes/tasks.py`](../src/pytegration/api/routes/tasks.py):

```python
@router.post("", response_model=TaskRead, status_code=201)
async def create_task(payload: TaskCreate, service: TaskServiceDep) -> TaskRead:
    return await service.create_task(payload)
```

- `payload: TaskCreate` — the request body, validated by Pydantic before your code
  runs. Invalid input → automatic `422` with details. You never write null checks.
- `service: TaskServiceDep` — dependency-injected (next section).
- `response_model=TaskRead` — the response is validated and any extra fields are
  stripped, so you can't accidentally leak internal data.

## Dependency Injection with `Depends`

A dependency is just a function FastAPI calls per request and injects the result.
See [`api/deps.py`](../src/pytegration/api/deps.py):

```python
SessionDep = Annotated[AsyncSession, Depends(get_session)]

def get_task_service(session: SessionDep) -> TaskService:
    return TaskService(TaskRepository(session))

TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
```

Dependencies can depend on other dependencies — FastAPI builds the graph and
tears it down (closing the DB session) automatically. Unlike Spring, there's no
classpath scanning: the wiring is **explicit and readable**, which makes it
trivial to substitute fakes in tests (via `app.dependency_overrides`).

## Request validation as a feature

Pydantic models with `extra="forbid"` and field constraints (`min_length`,
`ge`/`le`) mean malformed or hostile input is rejected at the edge — see
[`schemas/task.py`](../src/pytegration/schemas/task.py). This is both ergonomics
and security (Module 8).

## Try it

`make run`, then open <http://localhost:8000/docs> and call the endpoints from the
browser. That interactive page is generated entirely from your types.

➡️ Next: [Module 4 — Layered Architecture](04-layered-architecture.md)
