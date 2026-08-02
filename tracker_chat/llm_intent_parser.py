
from __future__ import annotations
from typing import Any

try:
    from tracker_config.settings import load_settings
    from tracker_llm.providers import build_provider
except Exception:
    load_settings = None
    build_provider = None

SUPPORTED_COMMANDS = {
    'create_workbook': ['output'],
    'render_workbook': ['source', 'output'],
    'summary': ['workbook', 'intern'],
    'extend_intern': ['source', 'intern', 'new_end', 'output'],
    'edit_task': ['source', 'intern', 'task_ref', 'theme', 'task', 'status', 'remarks', 'output'],
    'update_task_status': ['source', 'intern', 'task_ref', 'status', 'output'],
    'update_capstone': ['source', 'intern', 'title', 'objective', 'tech_stack', 'status', 'target_end', 'output'],
    'update_scenario': ['source', 'intern', 'scenario', 'skills', 'deliverable', 'assigned_week', 'due_date', 'status', 'output'],
    'edit_project': ['source', 'intern', 'project_number', 'title', 'description', 'assigned_date', 'due_date', 'status', 'output'],
    'update_project_status': ['source', 'intern', 'project_number', 'status', 'output'],
    'add_intern': ['source', 'spec', 'output'],
    'add_intern_with_plan': ['source', 'name', 'start_date', 'end_date', 'plan_name', 'manager', 'skip_manager', 'main_title', 'objective', 'tech_stack', 'scenario', 'skills', 'deliverable', 'output'],
    'add_holiday': ['source', 'name', 'date', 'scope', 'intern_name', 'output'],
    'edit_plan': ['source', 'plan_name', 'new_name', 'description', 'output'],
    'edit_plan_week': ['source', 'plan_name', 'week', 'theme', 'task', 'weekly_project', 'notes', 'output'],
}

class LLMIntentParser:
    """LLM-based parser for chat intent and field extraction.

    The parser returns structured command + args only. It never executes anything.
    Validation, missing-info questions, approval, audit logs, and execution remain
    in ChatService/CommandExecutor.
    """
    def __init__(self, env_path: str = '.env'):
        self.provider = None
        if load_settings and build_provider:
            try:
                settings = load_settings(env_path)
                if settings.ai_provider.lower() != 'mock':
                    self.provider = build_provider(settings)
            except Exception:
                self.provider = None

    def available(self) -> bool:
        return self.provider is not None

    def parse(self, message: str, active_command: str | None = None) -> dict[str, Any] | None:
        if not self.provider:
            return None
        command_hint = f"The user is replying to an active draft command: {active_command}. Fill missing fields for that command." if active_command else "No active draft command. Infer the best command."
        prompt = f"""
You are the intent parser for an internship tracker application.
Return ONLY valid JSON. Do not include markdown.

{command_hint}

User message:
{message}

Supported commands and allowed fields:
{SUPPORTED_COMMANDS}

Rules:
- Pick exactly one command from supported commands.
- If the user wants to add/create a new intern, use add_intern_with_plan. Do NOT use add_intern unless the user explicitly mentions JSON spec.
- If the user says "show progress of X", use summary with intern="X".
- If the user asks to create/draft/build a plan, and detailed week generation is needed, let the existing plan-drafting layer handle it by returning command="__plan_draft__".
- Normalize person names to title case, e.g. "shakeel" -> "Shakeel".
- Normalize statuses to one of: Pending, In Progress, Completed.
- Always convert any date the user gives, in whatever format (e.g. "14th July 2026", "July 14 2026", "14/07/2026"), to ISO yyyy-mm-dd.
- Do not invent dates that were not stated in some form by the user; only reformat ones that were. Do not invent workbook filenames or output filenames.
- Omit unknown fields.
- Return this shape:
{{"command":"...", "args":{{...}}, "reply":"short user-facing summary"}}
"""
        try:
            data = self.provider.complete_json(prompt)
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        command = data.get('command')
        if command == '__plan_draft__':
            return {'command': '__plan_draft__', 'args': {}, 'reply': data.get('reply','')}
        if command not in SUPPORTED_COMMANDS:
            return None
        args = data.get('args') or {}
        if not isinstance(args, dict):
            args = {}
        allowed = set(SUPPORTED_COMMANDS[command])
        safe_args = {k: v for k, v in args.items() if k in allowed and v not in [None, '']}
        return {'command': command, 'args': safe_args, 'reply': data.get('reply','')}
