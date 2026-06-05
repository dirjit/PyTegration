"""sandbox.py — Harness component #8: sandboxing & auth brokering (PLACEHOLDER).

> This is the security boundary of the harness. The model emits *intentions*
> (tool calls, code to run); the harness decides what actually executes and with
> what privileges. Get this wrong and a prompt injection becomes remote code
> execution on your infra.

This module is a deliberate PLACEHOLDER — it shows WHERE container/subprocess
sandboxing goes and states the rules, but the heavy lifting (a real container, a
seccomp profile, network egress control) is your Phase 3 / Phase 5 work. The
non-negotiable rules below are real and load-bearing even in the skeleton.

THE CARDINAL RULE
─────────────────
SECURITY: **NEVER `exec()` / `eval()` model-generated code in-process.** A string
the model produced is untrusted input. If the agent needs to run code, run it in
an isolated subprocess or container with no access to your process memory, your
secrets, or the host filesystem beyond an explicit mount.

AUTH BROKERING
──────────────
SECURITY: credentials (API keys, tokens) live in the HARNESS, never in the
sandbox and never in a tool argument the model controls. The harness injects auth
AFTER a request leaves the sandbox (the proxy pattern the Claude Agent SDK uses
for MCP/GitHub creds). Model-controlled code must never be able to read a secret,
even under prompt injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SandboxPolicy:
    """Declares what a sandboxed execution is allowed to touch.

    This is the *interface* a real sandbox enforces. The skeleton only checks the
    filesystem confinement (cheap, stdlib); network and resource limits are TODOs
    that require a real container/subprocess runtime.
    """

    workdir: Path  # the only directory tools may read/write
    allow_network: bool = False  # default-deny egress (allow-list in prod)
    allowed_hosts: list[str] = field(default_factory=list)
    cpu_seconds: int | None = None  # wall/CPU limit (enforced by the runtime)
    memory_mb: int | None = None  # memory cap (enforced by the runtime)


def confine_path(policy: SandboxPolicy, relative: str) -> Path:
    """Resolve `relative` inside the policy's workdir, refusing escapes.

    This is the ONE piece of sandboxing simple enough to do correctly in-process,
    and you should do it for every file tool. SECURITY: resolve symlinks and `..`
    then assert the result stays under `workdir`. A model will try `../../.ssh/`.
    """
    workdir = policy.workdir.resolve()
    candidate = (workdir / relative).resolve()
    if not candidate.is_relative_to(workdir):
        raise PermissionError(f"path escapes sandbox: {relative!r}")
    return candidate


def run_code_in_sandbox(policy: SandboxPolicy, code: str) -> str:
    """Run model-generated code under `policy`. PLACEHOLDER — not implemented.

    # TODO(student): implement this OUT OF PROCESS. Options, roughly in order of
    # isolation strength:
    #   1. `subprocess` with a restricted interpreter, dropped privileges, a
    #      tmpfs workdir, and `resource.setrlimit` CPU/memory caps.
    #   2. A container (Docker/Podman/gVisor) with no network, read-only rootfs,
    #      dropped capabilities, and only `policy.workdir` mounted.
    #   3. A microVM (Firecracker) or a hosted code-execution sandbox for
    #      untrusted code at scale.
    #
    # Whatever you choose, the invariant never changes:
    #   - NO in-process exec/eval of model output.
    #   - NO secrets reachable from inside.
    #   - Default-deny network; allow-list egress per `policy.allowed_hosts`.
    #   - Enforce CPU/memory/time limits so a runaway can't take the host down.
    """
    raise NotImplementedError(
        "Sandboxed code execution is a Phase 3/5 exercise. Implement it OUT OF "
        "PROCESS (subprocess/container). Never exec() model output in-process."
    )


class AuthBroker:
    """Holds credentials in the harness and injects them on outbound calls.

    PLACEHOLDER illustrating the pattern: the model/sandbox references a credential
    by *name* ("github", "search"); the broker maps the name to the actual secret
    and attaches it to the real request — so the secret value never enters the
    model's context or the sandbox.
    """

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        # In production, load from a secrets manager / env — NOT from code, and
        # NOT from anything the model can write to.
        self._secrets = secrets or {}

    def has(self, name: str) -> bool:
        return name in self._secrets

    def inject(self, name: str, request: dict[str, Any]) -> dict[str, Any]:
        """Attach the named credential to an outbound request's headers.

        # TODO(student): in a real broker this runs in a PROXY the sandbox cannot
        # bypass, so even compromised in-sandbox code can't read `self._secrets`.
        # Here we just demonstrate the name->secret indirection.
        """
        if name not in self._secrets:
            raise KeyError(f"no credential registered for {name!r}")
        headers = dict(request.get("headers", {}))
        headers["Authorization"] = f"Bearer {self._secrets[name]}"
        return {**request, "headers": headers}
