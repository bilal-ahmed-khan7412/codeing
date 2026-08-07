
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import os
import time

@dataclass
class Settings:
    ai_provider: str = "mock"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    llm_verify_ssl: bool = True
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout: int = 60
    http_user_agent: str = "InternTracker/0.7"


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() not in {"false", "0", "no", "off"}


def load_dotenv(path: str | Path = ".env") -> dict:
    env_path = Path(path)
    loaded = {}
    if not env_path.exists():
        return loaded
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
        loaded[key] = value
    return loaded


def ensure_env_secret(env_path: str | Path, var_name: str, generate: Callable[[], str]) -> str:
    """Atomically bootstrap a persisted secret into .env - safe against
    multiple processes starting at once (e.g. uvicorn --workers N). Without
    this, each process independently generates and appends its own value
    when one is missing, so different workers end up signing/decrypting
    with different keys - sessions or encrypted API keys created by one
    worker silently fail to validate/decrypt on another.

    Uses O_CREAT|O_EXCL as a cross-platform atomic "claim" - only the
    process that successfully creates the lock file generates the secret;
    everyone else waits briefly and reads back what the winner wrote.
    """
    env_path = Path(env_path)
    load_dotenv(env_path)
    value = os.getenv(var_name)
    if value:
        return value

    lock_path = Path(str(env_path) + f".{var_name}.lock")
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        for _ in range(50):
            time.sleep(0.1)
            load_dotenv(env_path)
            value = os.getenv(var_name)
            if value:
                return value
        # Lock holder never finished (crashed mid-write?) - fall through
        # and generate independently rather than hang forever.
    else:
        try:
            value = generate()
            os.environ[var_name] = value
            with env_path.open("a", encoding="utf-8") as f:
                f.write(f"\n{var_name}={value}\n")
            return value
        finally:
            try:
                lock_path.unlink()
            except OSError:
                pass

    value = generate()
    os.environ[var_name] = value
    with env_path.open("a", encoding="utf-8") as f:
        f.write(f"\n{var_name}={value}\n")
    return value


def load_settings(env_path: str | Path = ".env") -> Settings:
    load_dotenv(env_path)
    provider = os.getenv("AI_PROVIDER", "mock").strip().lower()
    return Settings(
        ai_provider=provider,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        llm_verify_ssl=_parse_bool(os.getenv("LLM_VERIFY_SSL"), True),
        llm_base_url=os.getenv("LLM_BASE_URL") or os.getenv("LOCAL_LLM_URL"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_model=os.getenv("LLM_MODEL"),
        llm_timeout=int(os.getenv("LLM_TIMEOUT", "60")),
        http_user_agent=os.getenv("HTTP_USER_AGENT", "InternTracker/0.7"),
    )
