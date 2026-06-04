# =============================================================================
# Makefile — the project task runner
# =============================================================================
# LESSON: Module 0 (Setup & Tooling). See docs/00-setup.md
#
# JAVA NOTE: think of these targets as Maven/Gradle lifecycle goals
#   (`mvn test`, `mvn verify`). Instead of remembering long command lines, you
#   run `make test`, `make lint`, `make all`. `make` is pre-installed on most
#   Unix systems, so it is a dependency-free way to standardize commands.
#
# SYNTAX TIP: each target's recipe lines MUST be indented with a TAB, not
#   spaces — a classic Makefile gotcha. `.PHONY` tells make these targets are
#   commands, not files to build.
# =============================================================================

# Use the virtualenv's tools if the venv exists, else fall back to PATH.
VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help setup migrate run test lint format type audit all docker-up clean

# Running `make` with no target prints this help (the `## ...` comments).
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv and install all dependencies (runtime + dev) + editable package
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .

migrate: ## Apply database migrations (create/update schema)
	$(VENV)/bin/alembic upgrade head

run: ## Start the API with hot-reload at http://localhost:8000 (docs at /docs)
	$(VENV)/bin/uvicorn pytegration.main:app --reload --port 8000

test: ## Run the full test suite (offline; forces the mock LLM provider)
	LLM_PROVIDER=mock $(VENV)/bin/pytest

lint: ## Lint the codebase with ruff
	$(VENV)/bin/ruff check .

format: ## Auto-format the codebase with ruff
	$(VENV)/bin/ruff format .

type: ## Static type-check the package with mypy
	$(VENV)/bin/mypy src

audit: ## Scan dependencies for known vulnerabilities
	$(VENV)/bin/pip-audit

# `make all` is the local equivalent of the CI gate: format check + lint + types + tests.
all: lint type test ## Run lint + type-check + tests (the CI gate)

docker-up: ## Build and run the app in Docker (serves on :8000)
	docker compose up --build

clean: ## Remove caches and local build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache *.egg-info build dist
	find . -type d -name __pycache__ -exec rm -rf {} +
