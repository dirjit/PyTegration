"""Authentication — API-key verification as a FastAPI dependency.

LESSON: Module 8 (Security). See docs/08-security.md
LAYER:  core

WHY an API key (and not JWT) for this teaching project?
    A shared API key lets us teach the FULL authn/authz mechanics — extracting a
    credential, comparing it safely, returning the right status codes — without
    the distraction of token signing, expiry, and key rotation. The dependency
    shape below is identical to what you'd use for JWT; only the verification body
    would change.
    PRODUCTION UPGRADE: for real multi-user systems, swap this for OAuth2/OIDC
    bearer tokens (FastAPI has `OAuth2PasswordBearer` / JWT helpers). The routes
    that depend on `require_api_key` would instead depend on `get_current_user`.

JAVA NOTE:
    `require_api_key` is the equivalent of a Spring Security filter / a method
    secured with `@PreAuthorize`. FastAPI runs it before the route handler.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Security
from fastapi.security import APIKeyHeader

from pytegration.api.deps import SettingsDep
from pytegration.core.errors import AuthError

# SYNTAX TIP: `APIKeyHeader` declares that credentials arrive in a header. With
#   `auto_error=False` we handle the missing-key case ourselves so the response
#   uses OUR error envelope (instead of FastAPI's default 403 shape). It also
#   documents the scheme in the OpenAPI "Authorize" dialog.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    settings: SettingsDep,
    provided_key: Annotated[str | None, Security(_api_key_header)] = None,
) -> None:
    """Reject the request unless a valid API key was supplied.

    SECURITY — why `secrets.compare_digest` instead of `==`?
        A normal string comparison short-circuits at the first differing byte, so
        the time it takes leaks how many leading characters were correct. An
        attacker can exploit that "timing side channel" to guess a secret byte by
        byte. `compare_digest` compares in CONSTANT time, closing that channel.

    Raises:
        AuthError: 401 if the key is missing or incorrect. (We deliberately do
            NOT reveal which — telling an attacker "key present but wrong" vs
            "key missing" is needless information.)
    """
    if provided_key is None or not secrets.compare_digest(provided_key, settings.api_key):
        raise AuthError("Missing or invalid API key.")
