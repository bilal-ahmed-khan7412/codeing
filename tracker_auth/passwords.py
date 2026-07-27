
from __future__ import annotations
import base64
import hashlib
import hmac
import os

PREFIX = 'pbkdf2_sha256'
ITERATIONS = 260000


def hash_password(password: str) -> str:
    """Return a salted PBKDF2-SHA256 password hash.

    Format: pbkdf2_sha256$iterations$salt$hash
    Uses only Python standard library, so no extra dependency is required.
    """
    password = password or ''
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return f"{PREFIX}${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def is_hashed(value: str) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX + '$')


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against hashed or legacy plain-text storage.

    Legacy plain-text support is included only for migration. When a plain-text
    password matches, caller should re-save it as a hash.
    """
    password = password or ''
    stored = stored or ''
    if not is_hashed(stored):
        return hmac.compare_digest(password, stored)
    try:
        _prefix, iterations, salt_b64, hash_b64 = stored.split('$', 3)
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(hash_b64.encode())
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iterations))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False
