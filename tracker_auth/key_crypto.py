from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet

from tracker_config.settings import ensure_env_secret

_ENV_PATH = Path(".env")


def _ensure_secret() -> str:
    # Persisted to .env so stored API keys stay decryptable across server
    # restarts - bootstrapped atomically so multiple worker processes
    # starting at once don't each generate a different key (see
    # ensure_env_secret's docstring).
    return ensure_env_secret(_ENV_PATH, "API_KEY_ENCRYPTION_SECRET", lambda: Fernet.generate_key().decode())


_FERNET = Fernet(_ensure_secret().encode())


def encrypt_api_key(raw: str) -> str:
    return _FERNET.encrypt(raw.encode()).decode()


def decrypt_api_key(token: str) -> str:
    return _FERNET.decrypt(token.encode()).decode()


def mask_api_key(raw: str) -> str:
    if not raw:
        return ''
    if len(raw) < 4:
        return '****'
    return f"{'*' * 8}{raw[-4:]}"
