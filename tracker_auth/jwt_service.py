from __future__ import annotations

import os
import secrets
import time
from pathlib import Path

import jwt

from tracker_config.settings import ensure_env_secret

_ENV_PATH = Path(".env")
_ALGORITHM = "HS256"
DEFAULT_SESSION_TTL_SECONDS = 8 * 60 * 60


def _ensure_secret() -> str:
    # Persisted to .env so sessions survive a server restart instead of
    # invalidating on every reload - bootstrapped atomically so multiple
    # worker processes starting at once don't each generate a different
    # secret (see ensure_env_secret's docstring).
    return ensure_env_secret(_ENV_PATH, "JWT_SECRET", lambda: secrets.token_hex(32))


_SECRET = _ensure_secret()
SESSION_TTL_SECONDS = int(os.getenv("JWT_SESSION_TTL_SECONDS", str(DEFAULT_SESSION_TTL_SECONDS)))


def create_session_token(user: dict, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user["id"]),
        "email": user.get("email", ""),
        "role": user.get("role", "User"),
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_session_token(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
