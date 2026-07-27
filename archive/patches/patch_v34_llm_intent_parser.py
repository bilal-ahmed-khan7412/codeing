from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_dir = root / 'tracker_chat'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0 after chat patches.')
chat_dir.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# 1) Add LLM intent parser. This improves routing/extraction and reduces regex brittleness.
# -----------------------------------------------------------------------------
(chat_dir / 'llm_intent_parser.py').write_text(r'''
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
- Use ISO dates yyyy-mm-dd exactly when provided.
- Do not invent dates, workbook filenames, or output filenames.
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
''', encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Patch ChatService to use LLMIntentParser before regex fallback.
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

# Add import.
if 'from tracker_chat.llm_intent_parser import LLMIntentParser' not in s:
    s = s.replace('from tracker_commands.executor import CommandExecutor', 'from tracker_commands.executor import CommandExecutor\nfrom tracker_chat.llm_intent_parser import LLMIntentParser')

# Add parser init.
if 'self.intent_parser = LLMIntentParser' not in s:
    s = s.replace('self.executor = CommandExecutor()\n', 'self.executor = CommandExecutor()\n        self.intent_parser = LLMIntentParser()\n')

# Patch message flow: current exact v0.15+ function.
old = """        # Groq/full LLM powered draft for free-form plan creation.\n        if self._looks_like_plan_request(text):\n            draft = self._draft_plan_with_llm(text, current_workbook)\n        else:\n            draft = self._build_rule_draft(text, current_workbook)\n        return self._response_for_draft(draft)\n"""
new = """        # Groq/full LLM powered draft for free-form plan creation.\n        # Keep this specialized path because it generates complete week content.\n        if self._looks_like_plan_request(text):\n            draft = self._draft_plan_with_llm(text, current_workbook)\n        else:\n            # For all other commands, use LLM structured intent parsing first.\n            # Regex/rules remain only as fallback.\n            draft = self._build_llm_intent_draft(text, current_workbook) or self._build_rule_draft(text, current_workbook)\n        return self._response_for_draft(draft)\n"""
if old in s:
    s = s.replace(old, new)
else:
    print('Warning: message flow block not matched. Attempting broad insert may be needed manually.')

# Add method _build_llm_intent_draft before _build_rule_draft.
if 'def _build_llm_intent_draft' not in s:
    method = r'''
    def _build_llm_intent_draft(self, text: str, current_workbook: str | None) -> ChatDraft | None:
        parsed = self.intent_parser.parse(text)
        if not parsed:
            return None
        command = parsed.get('command')
        if command == '__plan_draft__':
            return self._draft_plan_with_llm(text, current_workbook)
        args = parsed.get('args') or {}
        # Inject current workbook defaults. The LLM must not invent source/output paths.
        if current_workbook:
            if command == 'summary':
                args.setdefault('workbook', current_workbook)
            elif command != 'create_workbook':
                args.setdefault('source', current_workbook)
        self._defaults(command, args)
        return ChatDraft(str(uuid.uuid4()), command, args)

'''
    marker = '    def _build_rule_draft(self, text: str, current_workbook: str | None) -> ChatDraft:'
    if marker not in s:
        raise SystemExit('Could not find _build_rule_draft insertion point in tracker_chat/chat_service.py')
    s = s.replace(marker, method + marker)

# Patch fill_from_text to use LLM for follow-up to active draft before regex.
old = """        draft = self.drafts.get(draft_id)\n        if not draft:\n            return {'ok': False, 'error': 'Draft not found'}\n        lower = text.lower()\n        args = draft.args\n\n        # Common field extractions.\n"""
new = """        draft = self.drafts.get(draft_id)\n        if not draft:\n            return {'ok': False, 'error': 'Draft not found'}\n        # Try LLM field extraction for the active draft first. This avoids brittle\n        # issues such as lowercase names. Regex below remains fallback.\n        parsed = self.intent_parser.parse(text, active_command=draft.command)\n        if parsed and parsed.get('command') == draft.command:\n            for k, v in (parsed.get('args') or {}).items():\n                if v not in [None, '', []]:\n                    draft.args[k] = v\n            return self._response_for_draft(draft)\n        lower = text.lower()\n        args = draft.args\n\n        # Common field extractions.\n"""
if old in s and 'Try LLM field extraction for the active draft first' not in s:
    s = s.replace(old, new)

# Clean markdown from missing info message.
old = """        return f'I can prepare **{label}**, but I need: {\", \".join(missing)}. Please provide these values.'\n"""
new = """        return f'I can prepare {label}, but I need: {\", \".join(missing)}. Please provide these values.'\n"""
if old in s:
    s = s.replace(old, new)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) README note.
# -----------------------------------------------------------------------------
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.34 LLM structured intent parser

- Added `tracker_chat/llm_intent_parser.py`.
- Chat now uses Groq/LLM for command intent and field extraction before regex fallback.
- Fixes brittle parsing cases such as lowercase names:
  - `add intern shakeel ...`
  - `Add Shakeel ...`
  - `show progress of musab khan`
- Missing-info, Edit, Approve, Cancel, validation, audit logs, and CommandExecutor execution remain unchanged.
- Regex/rule parsing is still kept as fallback if the LLM provider is unavailable.
''', encoding='utf-8')

print('v0.34 LLM structured intent parser patch applied successfully.')
