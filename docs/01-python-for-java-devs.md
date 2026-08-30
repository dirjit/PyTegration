# Module 1 — Python for Java Developers

> **Goal:** translate your Java instincts into idiomatic Python, and learn the
> three "flavors of a class with fields" this project uses.

## Type hints + mypy = Java-like safety, opt-in

Python is dynamically typed, but modern Python adds **type hints** that a checker
(`mypy`) enforces statically — giving you much of `javac`'s safety.

```python
def add(a: int, b: int) -> int:   # like `int add(int a, int b)`
    return a + b
```

- `x: int | None` is `Optional<Integer>` — and mypy forces you to handle the
  `None` case before using it.
- We run mypy in **strict** mode (see `pyproject.toml`), so types are real.

**GOTCHA (`None` vs `null`):** use `is None` / `is not None`, never `== None`.
`is` checks identity (like Java `==` on references); `==` checks value equality
(like `.equals()`).

**GOTCHA (truthiness):** empty collections, `0`, `""`, and `None` are all "falsy".
`if items:` means "if the list is non-empty" — concise, but know the rule.

## Modules & packages

- A `.py` file is a **module**; a directory with `__init__.py` is a **package**.
  See [`src/pytegration/`](../src/pytegration).
- `from pytegration.services.task_service import TaskService` is a fully-qualified
  import — like `import com.example.services.TaskService`.
- There is no `public`/`private`. Convention: a leading underscore (`_helper`)
  means "internal, don't touch".

## The three flavors of "a class with fields"

This is the most important concept in the codebase. The same task data appears as
**three different classes**, each for a different job:

| Flavor | File | Java analog | Use it for |
|--------|------|-------------|------------|
| `@dataclass` | [`domain/models.py`](../src/pytegration/domain/models.py) | a `record` / POJO | framework-free business data |
| Pydantic `BaseModel` | [`schemas/task.py`](../src/pytegration/schemas/task.py) | a DTO + Bean Validation | validating data at the API edge |
| SQLAlchemy ORM | [`db/models.py`](../src/pytegration/db/models.py) | a JPA `@Entity` | mapping to a database table |

```python
@dataclass(frozen=True, slots=True)   # immutable like a Java record
class Task:
    id: int
    title: str
```

**Why three?** So a database column rename can't silently break your public API,
and your business rules don't depend on FastAPI or SQL. We cross between them
explicitly (e.g. `TaskRead.model_validate(orm_obj)` in the service layer).

## Enums

```python
class TaskStatus(StrEnum):   # a Java enum, but each member is also a string
    TODO = "todo"
```
See [`domain/enums.py`](../src/pytegration/domain/enums.py). `StrEnum` (Python
3.11+) makes each member a real `str`, so JSON/DB serialization is automatic. It
replaces the older `class TaskStatus(str, Enum)` idiom — and, unlike it,
`str(TaskStatus.TODO)` is `"todo"` rather than `"TaskStatus.TODO"`.

➡️ Next: [Module 2 — Async & Await](02-async-await.md)
