# Module 4 — Layered Architecture

> **Goal:** understand the layers, the dependency rule, and why both the REST API
> and the AI agent call the *same* service.

## The layers

```
            HTTP request
                 │
   ┌─────────────▼─────────────┐
   │  api/      (routers, DI)   │  HTTP in/out only. No business rules.
   ├───────────────────────────┤
   │  services/ (business logic)│  Rules, orchestration, DTO<->entity mapping.
   ├───────────────────────────┤
   │  repositories/ (data access)│ CRUD/queries. No rules, no HTTP.
   ├───────────────────────────┤
   │  db/       (engine, ORM)   │  SQLAlchemy session + models.
   └───────────────────────────┘

   domain/  + schemas/  are framework-light contracts used across layers.
   core/    is cross-cutting infrastructure (config, logging, security).
```

This is the same Controller → Service → Repository split you know from Spring.

## The dependency rule

**Dependencies point inward/downward only.** `api` may import `services`;
`services` may import `repositories`; nothing lower imports something higher. A
repository never imports a router. This is enforceable by eye (and by the import
graph) and is what keeps the system understandable.

A practical consequence: lower layers signal failures in **domain terms**, not
HTTP terms. The service raises `NotFoundError`
([`core/errors.py`](../src/pytegration/core/errors.py)); only the `api` layer (via
exception handlers) turns that into a `404`. Business code never imports FastAPI.

## DTO vs Entity

- `schemas/` holds **DTOs** — what crosses the wire.
- `db/models.py` holds **entities** — how data is stored.
- The **service** is the one place that maps between them
  (`TaskRead.model_validate(orm_obj)`), so a schema change and a column change stay
  decoupled.

## The payoff: one service, two callers

The single most important design decision in this project:

> Both [`api/routes/tasks.py`](../src/pytegration/api/routes/tasks.py) **and** the
> agent's tools in [`agent/tools.py`](../src/pytegration/agent/tools.py) call the
> **same** [`TaskService`](../src/pytegration/services/task_service.py).

Because the business rules live in exactly one place, the AI agent **cannot do
anything a normal API client couldn't** — a powerful security property we lean on
in Module 10. Add a rule once; both the API and the agent get it.

➡️ Next: [Module 5 — Persistence](05-persistence-sqlalchemy.md)
