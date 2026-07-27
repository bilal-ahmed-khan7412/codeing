
from __future__ import annotations
from dataclasses import dataclass
import json
import re
import requests
from tracker_config.settings import Settings
from tracker_llm.prompts import SYSTEM_PROMPT

class LLMProviderError(Exception):
    pass

class BaseLLMProvider:
    def complete_json(self, user_prompt: str) -> dict:
        raise NotImplementedError

class MockLLMProvider(BaseLLMProvider):
    """Rule-based fallback for quick tests without an API key."""
    def complete_json(self, user_prompt: str) -> dict:
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

    def complete_json(self, user_prompt: str) -> dict:
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
            "User-Agent": self.settings.http_user_agent,
            "Accept": "application/json",
        }
        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {"role":"system", "content": SYSTEM_PROMPT},
                {"role":"user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type":"json_object"},
        }
        res = requests.post(self.url, headers=headers, json=payload, timeout=self.settings.llm_timeout, verify=self.settings.llm_verify_ssl)
        if res.status_code >= 400:
            raise LLMProviderError(f"Groq error {res.status_code}: {res.text[:500]}")
        content = res.json()["choices"][0]["message"]["content"]
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

    def complete_json(self, user_prompt: str) -> dict:
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
                {"role":"system", "content": SYSTEM_PROMPT},
                {"role":"user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type":"json_object"},
        }
        res = requests.post(self.url, headers=headers, json=payload, timeout=self.settings.llm_timeout, verify=self.settings.llm_verify_ssl)
        if res.status_code >= 400:
            raise LLMProviderError(f"LLM error {res.status_code}: {res.text[:500]}")
        content = res.json()["choices"][0]["message"]["content"]
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
