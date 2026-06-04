"""db — persistence infrastructure (engine, session, ORM models).

LESSON: Module 5 (Persistence). See docs/05-persistence-sqlalchemy.md
LAYER:  db (infrastructure). The `repositories` layer talks to the database
        through the session defined here; nothing above `repositories` imports
        this package directly.
"""
