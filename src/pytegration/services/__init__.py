"""services — the business/application logic layer.

LESSON: Module 4 (Layered Architecture). See docs/04-layered-architecture.md
LAYER:  services. Orchestrates repositories, enforces business rules, and maps
        between ORM entities and Pydantic DTOs. It depends DOWN on repositories
        and domain types; it knows nothing about HTTP. The api layer and the AI
        agent both call services — so the rules live in exactly one place.

JAVA NOTE:
    Equivalent to a Spring `@Service`. The key discipline: HTTP concerns stay in
    controllers (api/), SQL concerns stay in repositories (db access), and the
    interesting decisions live here.
"""
