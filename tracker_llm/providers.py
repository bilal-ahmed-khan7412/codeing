
from __future__ import annotations
from dataclasses import dataclass, replace
import json
import re
import requests
from tracker_config.settings import Settings, load_settings

# The full command-routing SYSTEM_PROMPT (tracker_llm/prompts.py) interpolates all 19 command
# schemas (required/optional args + descriptions) - real, useful context
# for llm_cli.py's natural-language planner, whose actual job is picking
# one of those 19 commands. It was previously hardcoded as *every* call's
# system message regardless of task, so plan-drafting, intern-sheet
# drafting, and evaluation scoring were all paying ~1000+ tokens per call
# for command-schema text none of them use. Callers that don't need
# command routing now get this minimal default instead.
_DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Return ONLY valid JSON. No markdown, no extra commentary. "
    "Never invent file paths, workbook/source/output filenames, or any field value that is not "
    "clearly and explicitly present in the user's message - omit a field entirely rather than "
    "guessing at it from unrelated words in the text."
)

class LLMProviderError(Exception):
    pass


def _log_token_usage(model: str, response_json: dict) -> None:
    """Print per-call token usage from an OpenAI-compatible chat completion
    response, so LLM cost/consumption for a single request is visible in
    the server console / `docker compose logs` instead of being silently
    discarded. Uses print() rather than the logging module so it shows up
    with zero extra configuration.
    """
    usage = response_json.get("usage") or {}
    if not usage:
        return
    print(
        f"[LLM usage] model={model} "
        f"prompt_tokens={usage.get('prompt_tokens')} "
        f"completion_tokens={usage.get('completion_tokens')} "
        f"total_tokens={usage.get('total_tokens')}"
    )

class BaseLLMProvider:
    def complete_json(self, user_prompt: str, system_prompt: str | None = None) -> dict:
        raise NotImplementedError

class MockLLMProvider(BaseLLMProvider):
    """Rule-based fallback for quick tests without an API key."""
    def complete_json(self, user_prompt: str, system_prompt: str | None = None) -> dict:
        text = user_prompt.lower()
        # very small planner so tests can run offline
        if "extend" in text and "bilal" in text:
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", user_prompt)
            return {"command":"extend_intern", "args":{"intern":"Bilal Ahmad Khan", "new_end": m.group(1) if m else ""}}
        if "summary" in text:
            return {"command":"summary", "args":{}}
        if "scenario" in text and "bilal" in text:
            return {"command":"update_scenario", "args":{"intern":"Bilal Ahmad Khan"}}
        return {"command":"summary", "args":{}}

class GroqProvider(BaseLLMProvider):
    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.groq_api_key:
            raise LLMProviderError("GROQ_API_KEY is missing")
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def complete_json(self, user_prompt: str, system_prompt: str | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
            "User-Agent": self.settings.http_user_agent,
            "Accept": "application/json",
        }
        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {"role":"system", "content": system_prompt or _DEFAULT_SYSTEM_PROMPT},
                {"role":"user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type":"json_object"},
        }
        res = requests.post(self.url, headers=headers, json=payload, timeout=self.settings.llm_timeout, verify=self.settings.llm_verify_ssl)
        if res.status_code >= 400:
            raise LLMProviderError(f"Groq error {res.status_code}: {res.text[:500]}")
        data = res.json()
        _log_token_usage(self.settings.groq_model, data)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

class OpenAICompatibleProvider(BaseLLMProvider):
    """Provider for local/OpenAI-compatible servers.

    Expected endpoint: {base_url}/chat/completions or a full URL ending in /chat/completions.
    Works with local LLM servers that expose an OpenAI-compatible API.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.llm_base_url:
            raise LLMProviderError("LLM_BASE_URL or LOCAL_LLM_URL is missing")
        base = settings.llm_base_url.rstrip("/")
        self.url = base if base.endswith("/chat/completions") else base + "/chat/completions"

    def complete_json(self, user_prompt: str, system_prompt: str | None = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": self.settings.http_user_agent,
            "Accept": "application/json",
        }
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        payload = {
            "model": self.settings.llm_model or self.settings.groq_model,
            "messages": [
                {"role":"system", "content": system_prompt or _DEFAULT_SYSTEM_PROMPT},
                {"role":"user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type":"json_object"},
        }
        res = requests.post(self.url, headers=headers, json=payload, timeout=self.settings.llm_timeout, verify=self.settings.llm_verify_ssl)
        if res.status_code >= 400:
            raise LLMProviderError(f"LLM error {res.status_code}: {res.text[:500]}")
        data = res.json()
        _log_token_usage(self.settings.llm_model or self.settings.groq_model, data)
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

def build_provider(settings: Settings) -> BaseLLMProvider:
    provider = settings.ai_provider.lower()
    if provider == "groq":
        return GroqProvider(settings)
    if provider in {"local", "openai-compatible", "openai_compatible"}:
        return OpenAICompatibleProvider(settings)
    if provider == "mock":
        return MockLLMProvider()
    raise LLMProviderError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")


def build_provider_for_user(creds: dict) -> BaseLLMProvider | None:
    """Build a provider from a user's own stored provider/API key, or None
    if they haven't configured one (caller should fall back to the shared
    server default in that case).

    For 'groq'/'local', llm_base_url is never taken from the user - it's
    inherited from the server's own .env settings, since letting a user
    supply an arbitrary base URL would let them point the server's outbound
    HTTP request at an internal-only address (SSRF). The 'custom' provider
    is the deliberate exception: it exists specifically so a user can point
    at a genuine third-party OpenAI-compatible API (Gemini, etc.), so its
    base_url IS user-supplied - but only after passing is_public_http_url,
    both at save time (see user_service.update_profile) and again here at
    use time, in case the resolved address changed since it was saved.
    """
    provider_name = (creds.get('llm_provider') or '').strip().lower()
    encrypted = creds.get('llm_api_key_encrypted') or ''
    if not provider_name or not encrypted:
        return None
    from tracker_auth.key_crypto import decrypt_api_key
    api_key = decrypt_api_key(encrypted)
    base = load_settings('.env')
    if provider_name == 'groq':
        settings = replace(base, ai_provider='groq', groq_api_key=api_key, groq_model=creds.get('llm_model') or base.groq_model)
    elif provider_name in {'local', 'openai-compatible', 'openai_compatible'}:
        settings = replace(base, ai_provider='local', llm_api_key=api_key, llm_model=creds.get('llm_model') or base.llm_model)
    elif provider_name == 'custom':
        base_url = creds.get('llm_base_url') or ''
        from tracker_llm.url_safety import is_public_http_url
        if not is_public_http_url(base_url):
            return None
        settings = replace(base, ai_provider='local', llm_api_key=api_key, llm_base_url=base_url, llm_model=creds.get('llm_model') or base.llm_model)
    else:
        return None
    return build_provider(settings)
