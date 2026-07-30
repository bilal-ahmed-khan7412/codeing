
from tracker_config.settings import load_settings
from tracker_llm.providers import build_provider
from tracker_llm.prompts import SYSTEM_PROMPT
from tracker_commands.validator import CommandValidator, CommandValidationError

class LLMPlanner:
    def __init__(self, env_path: str = ".env"):
        self.settings = load_settings(env_path)
        self.provider = build_provider(self.settings)
        self.validator = CommandValidator()

    def plan(self, user_prompt: str, defaults: dict | None = None) -> dict:
        # Only this call site actually needs the full command-routing
        # schema (its job is choosing one of the 19 commands) - every
        # other complete_json() caller gets the provider's lightweight
        # default system prompt instead.
        payload = self.provider.complete_json(user_prompt, system_prompt=SYSTEM_PROMPT)
        payload.setdefault("args", {})
        # Defaults are filled by the app/session, for example source/output workbook path.
        # Important: app/session defaults must override LLM guesses for infrastructure fields.
        # The LLM should plan business intent, not decide file paths.
        if defaults:
            for key, value in defaults.items():
                if value not in [None, ""]:
                    payload["args"][key] = value
        return self.validator.validate(payload)
