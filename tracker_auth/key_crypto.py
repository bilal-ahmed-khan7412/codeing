from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

from tracker_config.settings import load_dotenv

_ENV_PATH = Path(".env")


def _ensure_secret() -> str:
    load_dotenv(_ENV_PATH)
    secret = os.getenv("API_KEY_ENCRYPTION_SECRET")
    if secret:
        return secret
    # No secret configured yet: generate one and persist it to .env so
    # stored API keys stay decryptable across server restarts.
    secret = Fernet.generate_key().decode()
    os.environ["API_KEY_ENCRYPTION_SECRET"] = secret
    with _ENV_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\nAPI_KEY_ENCRYPTION_SECRET={secret}\n")
    return secret


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
