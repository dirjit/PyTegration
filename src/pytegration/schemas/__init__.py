"""schemas — Pydantic models that define the API's request/response contract.

LESSON: Module 1 / Module 3. See docs/03-api-design-fastapi.md
LAYER:  schemas (the boundary). These are DTOs (Data Transfer Objects): the
        shapes that cross the HTTP wire. They are intentionally separate from
        the ORM models in `db/` and the domain types in `domain/`.

WHY three kinds of "model"?
    - schemas/  -> Pydantic DTOs:   what the API accepts and returns (validated).
    - db/models -> SQLAlchemy ORM:  how data is stored in tables.
    - domain/   -> plain dataclasses: framework-free business entities.
    Keeping them separate means a database column rename does not silently break
    your public API, and your business rules do not depend on FastAPI or SQL.
    JAVA NOTE: this is the classic DTO-vs-Entity separation you would enforce
    with MapStruct/ModelMapper in a Spring app.
"""
