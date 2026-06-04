"""domain — framework-free business types (enums and entities).

LESSON: Module 1 / Module 4. See docs/04-layered-architecture.md
LAYER:  domain (the innermost layer). It depends on NOTHING in the app — not
        FastAPI, not SQLAlchemy. That independence is deliberate: business
        concepts should outlive any framework choice.

JAVA NOTE:
    This is your "domain model" in Domain-Driven Design terms — plain types with
    no persistence or web annotations, the equivalent of POJOs/records kept free
    of JPA or Spring imports.
"""
