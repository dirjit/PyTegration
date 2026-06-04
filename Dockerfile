# =============================================================================
# Dockerfile — a small, secure, multi-stage image for the API
# =============================================================================
# LESSON: Module 0 / Module 8. See docs/00-setup.md and docs/08-security.md
#
# JAVA NOTE: a multi-stage build is like building a fat JAR in one stage and
#   copying only the JAR into a slim runtime image — you ship the artifact, not
#   the whole build toolchain. Here the "artifact" is a populated virtualenv.
#
# WHY multi-stage? The builder stage has compilers and caches; the final image
#   contains only the runtime + installed package, so it is smaller and has less
#   attack surface.
# =============================================================================

# ----- Stage 1: build a virtualenv with all runtime dependencies -------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install runtime deps first (this layer is cached unless requirements change).
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Then install our own package into the same venv.
COPY pyproject.toml README.md ./
COPY src ./src
RUN /opt/venv/bin/pip install --no-cache-dir .

# ----- Stage 2: the lean runtime image ---------------------------------------
FROM python:3.11-slim AS runtime

# SECURITY: run as a NON-ROOT user. If the app is ever compromised, the attacker
#   does not get root inside the container.
RUN useradd --create-home --uid 10001 app

# Copy only what we need to run: the populated venv + migration assets.
COPY --from=builder /opt/venv /opt/venv
COPY migrations /app/migrations
COPY alembic.ini /app/alembic.ini

# A writable data dir owned by the app user (the SQLite file lives here). A named
# volume mounted here inherits this ownership, so the app can write to it.
RUN mkdir /data && chown app:app /data

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL="sqlite+aiosqlite:////data/pytegration.db"

USER app
EXPOSE 8000

# Default: serve the API. (docker-compose runs migrations first; see that file.)
CMD ["uvicorn", "pytegration.main:app", "--host", "0.0.0.0", "--port", "8000"]
