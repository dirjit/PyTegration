"""persistence.py — Harness component #4: durable memory / checkpointing.

> An agent that loses its state on a process restart is a toy. A production
> harness *checkpoints* after every step so a crash, a deploy, or a 2am OOM-kill
> can be resumed instead of restarted.

This module is WORKING, using only stdlib `sqlite3`. After each step the loop
calls `save_step(...)`; to resume, call `load_run(run_id)` and continue from the
last checkpoint. This is the durable-execution idea behind LangGraph's
checkpointer, built by hand.

In context-primitive terms this is WRITE taken to its limit: state persisted
OUTSIDE the window AND outside the process, surviving across runs.

SECURITY: checkpoints contain the full conversation — treat the DB as sensitive.
Don't persist secrets the model surfaced (pair with a redaction post_tool hook).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Checkpoint:
    run_id: str
    iteration: int
    messages: list[dict[str, Any]]
    status: str  # "running" | "done" | "stopped" | "error"
    updated_at: float


class Checkpointer:
    """SQLite-backed checkpoint store. One row per (run_id) holding latest state,
    plus an append-only step log for replay/debugging.

    Usage:
        cp = Checkpointer("runs.db")
        cp.start_run("run-123", messages)
        ... loop ...
        cp.save_step("run-123", iteration, messages, status="running")
        # later / after a crash:
        ckpt = cp.load_run("run-123")
        if ckpt: resume from ckpt.iteration with ckpt.messages
    """

    def __init__(self, db_path: str | Path = "harness_runs.db") -> None:
        self._db_path = str(db_path)
        # `check_same_thread=False` keeps the demo simple; in async/threaded prod
        # use a connection-per-task or a small pool.
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id     TEXT PRIMARY KEY,
                iteration  INTEGER NOT NULL,
                messages   TEXT    NOT NULL,   -- JSON
                status     TEXT    NOT NULL,
                updated_at REAL    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS steps (
                run_id     TEXT    NOT NULL,
                iteration  INTEGER NOT NULL,
                messages   TEXT    NOT NULL,   -- JSON snapshot at this step
                status     TEXT    NOT NULL,
                created_at REAL    NOT NULL,
                PRIMARY KEY (run_id, iteration)
            );
            """
        )
        self._conn.commit()

    def start_run(self, run_id: str, messages: list[dict[str, Any]]) -> None:
        """Create (or reset) a run at iteration 0."""
        now = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, iteration, messages, status, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (run_id, 0, json.dumps(messages), "running", now),
        )
        self._conn.commit()

    def save_step(
        self,
        run_id: str,
        iteration: int,
        messages: list[dict[str, Any]],
        status: str = "running",
    ) -> None:
        """Checkpoint after a step: update the run's latest state AND append to the
        step log. Called by the loop every iteration — this is the durability
        guarantee. A crash after this returns can resume from `iteration`."""
        now = time.time()
        payload = json.dumps(messages)
        with self._conn:  # transaction: both writes commit together or not at all
            self._conn.execute(
                "UPDATE runs SET iteration=?, messages=?, status=?, updated_at=? WHERE run_id=?",
                (iteration, payload, status, now, run_id),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO steps"
                " (run_id, iteration, messages, status, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (run_id, iteration, payload, status, now),
            )

    def load_run(self, run_id: str) -> Checkpoint | None:
        """Load the latest checkpoint for a run, or None if it doesn't exist.

        This is the RESUME path: hand the returned `messages` and `iteration`
        back to the loop and it picks up where it left off.
        """
        row = self._conn.execute(
            "SELECT run_id, iteration, messages, status, updated_at FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return Checkpoint(
            run_id=row["run_id"],
            iteration=row["iteration"],
            messages=json.loads(row["messages"]),
            status=row["status"],
            updated_at=row["updated_at"],
        )

    def history(self, run_id: str) -> list[Checkpoint]:
        """Return every step snapshot for a run (for replay / time-travel debugging).

        TODO(student): this is the foundation for LangGraph-style "time travel" —
        let a developer rewind to step N, edit the state, and re-run forward.
        """
        rows = self._conn.execute(
            "SELECT run_id, iteration, messages, status, created_at FROM steps"
            " WHERE run_id=? ORDER BY iteration",
            (run_id,),
        ).fetchall()
        return [
            Checkpoint(
                run_id=r["run_id"],
                iteration=r["iteration"],
                messages=json.loads(r["messages"]),
                status=r["status"],
                updated_at=r["created_at"],
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
