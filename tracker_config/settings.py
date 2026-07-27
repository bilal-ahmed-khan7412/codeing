
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os

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
