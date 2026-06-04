"""core — cross-cutting infrastructure (config, logging, security, errors).

LESSON: Module 6 / Module 8 / Module 9.
LAYER:  core (infrastructure). Contains NO business logic and NO HTTP routes;
        everything else may depend on `core`, but `core` depends on nothing in
        the app above it. Keeping the dependency arrows pointing inward is what
        makes the codebase easy to reason about (see docs/04-layered-architecture.md).
"""
