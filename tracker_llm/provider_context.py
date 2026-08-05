from __future__ import annotations

from contextvars import ContextVar

# Holds the per-request LLM provider override (set by ChatService's public
# entry points when the acting user has their own AI provider/API key
# configured). Call-scoped via ContextVar rather than instance state on
# ChatService/LLMIntentParser/InternSheetDrafter, since those are singletons
# shared across concurrent requests from different users (sync routes run in
# FastAPI's threadpool) - mutating a shared self.provider per-request would
# race between users.
current_provider: ContextVar = ContextVar('current_provider', default=None)
