from __future__ import annotations

import os
import secrets
import time
from pathlib import Path

import jwt

from tracker_config.settings import load_dotenv

_ENV_PATH = Path(".env")
_ALGORITHM = "HS256"
DEFAULT_SESSION_TTL_SECONDS = 8 * 60 * 60


def _ensure_secret() -> str:
    load_dotenv(_ENV_PATH)
    secret = os.getenv("JWT_SECRET")
    if secret:
        return secret
    # No secret configured yet: generate one and persist it to .env so
    # sessions survive a server restart instead of invalidating on every reload.
    secret = secrets.token_hex(32)
    os.environ["JWT_SECRET"] = secret
    with _ENV_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\nJWT_SECRET={secret}\n")
    return secret


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
