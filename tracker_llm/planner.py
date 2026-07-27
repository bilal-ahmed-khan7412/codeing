
from tracker_config.settings import load_settings
from tracker_llm.providers import build_provider
from tracker_commands.validator import CommandValidator, CommandValidationError

class LLMPlanner:
    def __init__(self, env_path: str = ".env"):
        self.settings = load_settings(env_path)
        self.provider = build_provider(self.settings)
        self.validator = CommandValidator()

    def plan(self, user_prompt: str, defaults: dict | None = None) -> dict:
        payload = self.provider.complete_json(user_prompt)
        payload.setdefault("args", {})
        # Defaults are filled by the app/session, for example source/output workbook path.
        # Important: app/session defaults must override LLM guesses for infrastructure fields.
        # The LLM should plan business intent, not decide file paths.
        if defaults:
            for key, value in defaults.items():
                if value not in [None, ""]:
                    payload["args"][key] = value
        return self.validator.validate(payload)
