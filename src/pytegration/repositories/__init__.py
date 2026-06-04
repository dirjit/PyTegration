"""repositories — the data-access layer (CRUD over the database session).

LESSON: Module 4 / Module 5. See docs/04-layered-architecture.md
LAYER:  repositories. Sits BETWEEN services and db. A repository knows how to
        read/write rows; it does NOT know business rules (services' job) or HTTP
        (api's job). This separation means you could swap SQLite for Postgres, or
        even an in-memory store, without touching service or api code.

JAVA NOTE:
    Equivalent to a Spring Data `Repository` / DAO — except we write the methods
    explicitly so you can see exactly what SQL the ORM runs.
"""
