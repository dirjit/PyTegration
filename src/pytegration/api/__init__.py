"""api — the HTTP layer: FastAPI routers and dependency-injection wiring.

LESSON: Module 3 / Module 4. See docs/03-api-design-fastapi.md
LAYER:  api (the outermost layer). It translates HTTP <-> Python by calling the
        `services` layer. It must NOT contain business rules and must NOT talk to
        the database directly — those belong to `services` and `repositories`.
"""
