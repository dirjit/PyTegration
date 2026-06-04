# Module 0 — Setup & Tooling

> **Goal:** get the project running, and understand the Python toolchain by
> mapping it onto the Java/Maven world you already know.

## The mental model

| Python | Java analog | Role |
|--------|-------------|------|
| `python3 -m venv .venv` | a clean, per-project JDK + local `.m2` | isolated environment |
| `pip` | Maven/Gradle dependency resolver | installs packages |
| `pyproject.toml` | `pom.xml` | project metadata + tool config |
| `requirements.txt` | a resolved/locked dependency tree | pinned, reproducible installs |
| `Makefile` | Maven lifecycle goals (`mvn test`) | task shortcuts |
| `ruff` | Checkstyle + Spotless | lint + format |
| `mypy` | `javac` type checking | static type safety |
| `pytest` | JUnit | tests |

## Virtual environments (the #1 thing to internalize)

Python installs packages **globally** by default, which causes version clashes
between projects. A **virtual environment** is a private folder (`.venv/`) with
its own interpreter and packages — like giving each project its own `.m2`.

```bash
python3 -m venv .venv          # create it
source .venv/bin/activate      # use it (your shell's `python` now points inside)
```

**GOTCHA:** if you forget to activate, `pip install` pollutes your system Python.
The `Makefile` targets always call the venv's tools by full path (`.venv/bin/...`)
so they work whether or not you've activated.

## `pyproject.toml` vs `requirements.txt`

- [`pyproject.toml`](../pyproject.toml) declares **abstract** dependencies with
  loose ranges (the *contract*), plus all tool config. This is your `pom.xml`.
- [`requirements.txt`](../requirements.txt) pins **exact** versions (the *lock*).
  Production installs from here so every machine gets identical bytes.

**Editable install** (`pip install -e .`): installs *our* package as a live link
to `src/`, so code edits take effect without reinstalling. The `src/` layout
forces this step, which is exactly why we use it (see `pyproject.toml` comments).

## Run it

```bash
make setup      # venv + install everything + editable install
cp .env.example .env
make migrate    # create the database schema
make run        # http://localhost:8000/docs
make all        # lint + type-check + test (the CI gate)
```

## Why this matters

A reproducible, isolated, type-checked, linted setup is the foundation of every
production Python project. Everything in the later modules assumes it.

➡️ Next: [Module 1 — Python for Java Devs](01-python-for-java-devs.md)
