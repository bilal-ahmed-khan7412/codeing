from pathlib import Path

root = Path(__file__).resolve().parent

# -----------------------------------------------------------------------------
# 1) Add create_plan_from_draft to PlanService
# -----------------------------------------------------------------------------
plan_service = root / 'tracker_services' / 'plan_service.py'
if not plan_service.exists():
    raise SystemExit('tracker_services/plan_service.py not found. Apply this patch inside intern_tracker_system_v0 after v0.13/v0.14.')

s = plan_service.read_text(encoding='utf-8')
if 'def create_plan_from_draft' not in s:
    insert = r'''
    def create_plan_from_draft(self, source_path: str, plan_name: str, description: str = '', weeks: list | None = None, output_path: str | None = None) -> CommandResult:
        """Create a complete plan from an LLM/user-approved draft.

        weeks should be a list of dicts:
        {"week": 1, "theme": "...", "task": "...", "weekly_project": "...", "notes": "..."}
        """
        data = parse_workbook(source_path)
        if self._find_plan(data, plan_name):
            return CommandResult(False, f'Plan already exists: {plan_name}')
        weeks = weeks or []
        headers = ['Week', 'Theme', 'Task', 'Weekly Project', 'Notes']
        rows = []
        for idx, item in enumerate(weeks, start=1):
            if not isinstance(item, dict):
                continue
            rows.append([
                int(item.get('week') or idx),
                item.get('theme', ''),
                item.get('task', ''),
                item.get('weekly_project', ''),
                item.get('notes', ''),
            ])
        if not rows:
            rows = [[i, '', '', '', ''] for i in range(1, 9)]
        sheet_name = self._safe_sheet_name(plan_name)
        plan = PlanSheetData(
            title=f'Plan — {plan_name}',
            subtitle=description,
            headers=headers,
            rows=rows,
            sheet_name=sheet_name,
            plan_type='weekly_custom'
        )
        data.plans.append(plan)
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f'Created draft plan {plan_name}: {out}', out)

'''
    marker = '    def create_plan('
    if marker not in s:
        raise SystemExit('Could not find create_plan insertion point in plan_service.py')
    s = s.replace(marker, insert + marker)
    plan_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Register command and executor support
# -----------------------------------------------------------------------------
registry = root / 'tracker_commands' / 'registry.py'
s = registry.read_text(encoding='utf-8')
if '"create_plan_from_draft"' not in s:
    s = s.replace('COMMAND_SCHEMAS = {\n', 'COMMAND_SCHEMAS = {\n    "create_plan_from_draft": {"required": ["source", "plan_name", "weeks", "output"], "optional": ["description"], "description": "Create a full plan from an approved LLM draft."},\n')
    registry.write_text(s, encoding='utf-8')

executor = root / 'tracker_commands' / 'executor.py'
s = executor.read_text(encoding='utf-8')
if 'command == "create_plan_from_draft"' not in s:
    s = s.replace('        if command == "create_plan":\n', '        if command == "create_plan_from_draft":\n            return self.plan_service.create_plan_from_draft(args["source"], args["plan_name"], args.get("description", ""), args.get("weeks", []), args.get("output"))\n        if command == "create_plan":\n')
    executor.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Replace tracker_chat/chat_service.py with Groq-aware draft service
# -----------------------------------------------------------------------------
chat_dir = root / 'tracker_chat'
chat_dir.mkdir(exist_ok=True)
(chat_dir / '__init__.py').write_text('', encoding='utf-8')
(chat_dir / 'chat_service.py').write_text(r'''
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
import uuid
from typing import Any

from tracker_commands.executor import CommandExecutor

try:
    from tracker_config.settings import load_settings
    from tracker_llm.providers import build_provider
except Exception:
    load_settings = None
    build_provider = None

COMMAND_LABELS = {
    'create_workbook': 'Create Fresh Workbook',
    'render_workbook': 'Render/Clean Uploaded Workbook',
    'summary': 'Generate Progress Summary',
    'extend_intern': 'Extend Intern',
    'edit_task': 'Edit Task',
    'update_task_status': 'Update Task Status',
    'update_capstone': 'Update Capstone/Main Project',
    'update_scenario': 'Update Real-World Scenario',
    'edit_project': 'Edit Weekly/Small Project',
    'update_project_status': 'Update Project Status',
    'add_intern': 'Add Intern From JSON Spec',
    'add_intern_basic': 'Add Intern (Form)',
    'add_holiday': 'Add Holiday',
    'create_plan': 'Create Plan',
    'create_plan_from_draft': 'Create Plan From LLM Draft',
    'edit_plan': 'Edit Plan',
    'edit_plan_week': 'Edit Plan Week',
    'apply_plan_to_intern': 'Apply Plan to Intern',
}

REQUIRED = {
    'create_workbook': ['output'],
    'render_workbook': ['source', 'output'],
    'summary': ['workbook'],
    'extend_intern': ['source', 'intern', 'new_end', 'output'],
    'edit_task': ['source', 'intern', 'task_ref', 'output'],
    'update_task_status': ['source', 'intern', 'task_ref', 'status', 'output'],
    'update_capstone': ['source', 'intern', 'output'],
    'update_scenario': ['source', 'intern', 'output'],
    'edit_project': ['source', 'intern', 'project_number', 'output'],
    'update_project_status': ['source', 'intern', 'project_number', 'status', 'output'],
    'add_intern': ['source', 'spec', 'output'],
    'add_intern_basic': ['source', 'name', 'start_date', 'end_date', 'output'],
    'add_holiday': ['source', 'name', 'date', 'output'],
    'create_plan': ['source', 'plan_name', 'output'],
    'create_plan_from_draft': ['source', 'plan_name', 'weeks', 'output'],
    'edit_plan': ['source', 'plan_name', 'output'],
    'edit_plan_week': ['source', 'plan_name', 'week', 'output'],
    'apply_plan_to_intern': ['source', 'intern', 'plan_name', 'output'],
}

@dataclass
class ChatDraft:
    draft_id: str
    command: str
    args: dict[str, Any] = field(default_factory=dict)
    status: str = 'drafting'
    summary: str = ''

class ChatService:
    def __init__(self):
        self.drafts: dict[str, ChatDraft] = {}
        self.executor = CommandExecutor()
        self.provider = None
        if load_settings and build_provider:
            try:
                settings = load_settings('.env')
                if settings.ai_provider.lower() != 'mock':
                    self.provider = build_provider(settings)
            except Exception:
                self.provider = None

    def message(self, text: str, current_workbook: str | None = None) -> dict:
        # Groq/full LLM powered draft for free-form plan creation.
        if self._looks_like_plan_request(text):
            draft = self._draft_plan_with_llm(text, current_workbook)
        else:
            draft = self._build_rule_draft(text, current_workbook)
        return self._response_for_draft(draft)

    def update_draft(self, draft_id: str, args: dict) -> dict:
        draft = self.drafts.get(draft_id)
        if not draft:
            return {'ok': False, 'error': 'Draft not found'}
        for k, v in args.items():
            if v not in [None, '']:
                if k == 'weeks' and isinstance(v, str):
                    try:
                        v = json.loads(v)
                    except Exception:
                        pass
                draft.args[k] = v
        return self._response_for_draft(draft)

    def approve(self, draft_id: str) -> dict:
        draft = self.drafts.get(draft_id)
        if not draft:
            return {'ok': False, 'error': 'Draft not found'}
        missing = self._missing(draft)
        if missing:
            return {'ok': False, 'error': f'Missing fields: {", ".join(missing)}'}
        result = self.executor.execute({'command': draft.command, 'args': draft.args})
        return {
            'ok': result.ok,
            'message': result.message,
            'output_path': result.output_path,
            'data': result.data,
        }

    def cancel(self, draft_id: str) -> dict:
        self.drafts.pop(draft_id, None)
        return {'ok': True, 'message': 'Draft cancelled'}

    def _response_for_draft(self, draft: ChatDraft) -> dict:
        missing = self._missing(draft)
        if missing:
            draft.status = 'needs_more_info'
            self.drafts[draft.draft_id] = draft
            return {
                'ok': True,
                'type': 'needs_more_info',
                'draft_id': draft.draft_id,
                'message': self._question(draft.command, missing),
                'missing': missing,
                'known_args': draft.args,
                'command': draft.command,
            }
        draft.status = 'awaiting_approval'
        draft.summary = self._summary(draft)
        self.drafts[draft.draft_id] = draft
        return {
            'ok': True,
            'type': 'proposal',
            'draft_id': draft.draft_id,
            'message': draft.summary,
            'command': draft.command,
            'label': COMMAND_LABELS.get(draft.command, draft.command),
            'args': draft.args,
        }

    def _looks_like_plan_request(self, text: str) -> bool:
        lower = text.lower()
        return 'plan' in lower and not any(x in lower for x in ['edit plan', 'apply plan', 'plan week', 'rename plan'])

    def _draft_plan_with_llm(self, text: str, current_workbook: str | None) -> ChatDraft:
        fallback_name = self._extract_plan_name(text) or 'LLM Generated Plan'
        weeks_count = self._extract_weeks_count(text) or 8
        source = current_workbook or ''
        output = f"Plan_{self._safe_name(fallback_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        if self.provider:
            try:
                prompt = f"""
Create a practical intern learning plan from this request:
{text}

Return ONLY JSON with this exact shape:
{{
  "plan_name": "short plan name",
  "description": "one sentence description",
  "weeks": [
    {{"week": 1, "theme": "...", "task": "...", "weekly_project": "...", "notes": "..."}}
  ]
}}
Rules:
- Create {weeks_count} weeks unless user clearly asked otherwise.
- Intern plan should be practical, beginner-friendly if level is unclear.
- Do not include markdown.
"""
                data = self.provider.complete_json(prompt)
                plan_name = data.get('plan_name') or fallback_name
                description = data.get('description') or text
                weeks = data.get('weeks') or []
                return ChatDraft(str(uuid.uuid4()), 'create_plan_from_draft', {
                    'source': source,
                    'plan_name': plan_name,
                    'description': description,
                    'weeks': weeks,
                    'output': output,
                })
            except Exception as e:
                # Fall back to deterministic draft but expose the error in notes.
                weeks = self._fallback_weeks(fallback_name, weeks_count, f'LLM draft failed: {e}')
        else:
            weeks = self._fallback_weeks(fallback_name, weeks_count, '')
        return ChatDraft(str(uuid.uuid4()), 'create_plan_from_draft', {
            'source': source,
            'plan_name': fallback_name,
            'description': text,
            'weeks': weeks,
            'output': output,
        })

    def _fallback_weeks(self, plan_name: str, count: int, note: str) -> list[dict]:
        return [
            {'week': i, 'theme': f'{plan_name} Week {i}', 'task': 'Task to be assigned', 'weekly_project': f'Week {i}: Project to be assigned', 'notes': note}
            for i in range(1, count + 1)
        ]

    def _build_rule_draft(self, text: str, current_workbook: str | None) -> ChatDraft:
        lower = text.lower()
        command = self._detect_command(lower)
        args: dict[str, Any] = {}
        if current_workbook:
            if command == 'summary':
                args['workbook'] = current_workbook
            elif command != 'create_workbook':
                args['source'] = current_workbook
        self._extract_common(text, lower, command, args)
        self._defaults(command, args)
        return ChatDraft(str(uuid.uuid4()), command, args)

    def _detect_command(self, lower: str) -> str:
        if 'clean' in lower or 'render' in lower: return 'render_workbook'
        if 'summary' in lower or 'progress' in lower or 'report' in lower: return 'summary'
        if 'holiday' in lower: return 'add_holiday'
        if 'extend' in lower: return 'extend_intern'
        if 'task status' in lower or ('mark' in lower and 'task' in lower): return 'update_task_status'
        if 'edit task' in lower or ('change' in lower and 'task' in lower): return 'edit_task'
        if 'capstone' in lower or 'main project' in lower: return 'update_capstone'
        if 'scenario' in lower: return 'update_scenario'
        if 'project status' in lower: return 'update_project_status'
        if 'edit project' in lower or 'weekly project' in lower or 'small project' in lower: return 'edit_project'
        if 'json' in lower and 'intern' in lower: return 'add_intern'
        if 'add intern' in lower or 'create intern' in lower: return 'add_intern_basic'
        if 'apply plan' in lower or ('apply' in lower and 'plan' in lower): return 'apply_plan_to_intern'
        if 'edit plan week' in lower or ('week' in lower and 'plan' in lower and 'edit' in lower): return 'edit_plan_week'
        if 'edit plan' in lower or 'rename plan' in lower: return 'edit_plan'
        if 'fresh workbook' in lower or 'blank workbook' in lower or 'create workbook' in lower: return 'create_workbook'
        return 'summary'

    def _extract_common(self, text: str, lower: str, command: str, args: dict):
        dates = re.findall(r'20\d{2}-\d{2}-\d{2}', text)
        if command == 'extend_intern' and dates: args['new_end'] = dates[-1]
        if command == 'add_holiday' and dates: args['date'] = dates[-1]
        if command == 'add_intern_basic':
            if len(dates) >= 1: args['start_date'] = dates[0]
            if len(dates) >= 2: args['end_date'] = dates[1]
        if command in ['edit_task','update_task_status'] and dates: args['task_ref'] = dates[0]
        m = re.search(r'(?:intern|for|named|name)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
        if m and command in ['extend_intern','edit_task','update_task_status','update_capstone','update_scenario','edit_project','update_project_status','apply_plan_to_intern']:
            args['intern'] = m.group(1).strip()
        if command == 'add_intern_basic':
            m2 = re.search(r'(?:named|name|intern)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text)
            if m2: args['name'] = m2.group(1).strip()
        if 'completed' in lower: args['status'] = 'Completed'
        elif 'in progress' in lower: args['status'] = 'In Progress'
        elif 'pending' in lower: args['status'] = 'Pending'
        wm = re.search(r'week\s+(\d+)', lower)
        if wm: args['week'] = int(wm.group(1))
        pm = re.search(r'project\s+#?\s*(\d+)', lower)
        if pm: args['project_number'] = int(pm.group(1))
        if command == 'add_holiday':
            hm = re.search(r'holiday(?: named| called)?\s+([A-Za-z0-9 ._-]+)', text, re.I)
            args['name'] = hm.group(1).strip() if hm else 'Holiday'

    def _defaults(self, command: str, args: dict):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if command == 'create_workbook': args.setdefault('output', f'Blank_Intern_Tracker_{stamp}.xlsx')
        elif command != 'summary': args.setdefault('output', f'{command}_{stamp}.xlsx')
        if command == 'add_holiday': args.setdefault('scope', 'global')

    def _missing(self, draft: ChatDraft) -> list[str]:
        return [k for k in REQUIRED.get(draft.command, []) if draft.args.get(k) in [None, '', []]]

    def _question(self, command: str, missing: list[str]) -> str:
        label = COMMAND_LABELS.get(command, command)
        return f'I can prepare **{label}**, but I need: {", ".join(missing)}. Please provide these values.'

    def _summary(self, draft: ChatDraft) -> str:
        lines = [f'Proposal: **{COMMAND_LABELS.get(draft.command, draft.command)}**', '', 'I will execute this command after approval:', '']
        for k, v in draft.args.items():
            if k == 'weeks' and isinstance(v, list):
                lines.append(f'- weeks: {len(v)} week(s) drafted')
                for item in v[:10]:
                    if isinstance(item, dict):
                        lines.append(f"  - Week {item.get('week')}: {item.get('theme')} | {item.get('weekly_project')}")
            else:
                lines.append(f'- {k}: {v}')
        lines.append('')
        lines.append('Approve this action?')
        return '\n'.join(lines)

    def _extract_plan_name(self, text: str) -> str | None:
        m = re.search(r'(?:called|named|for|plan for|plan called)\s+([A-Za-z0-9 ._+-]+)', text, re.I)
        if m:
            return m.group(1).strip().rstrip('.')
        words = text.split()
        for w in words:
            if w.lower() not in ['create','make','an','a','plan','week','weeks','for'] and w[:1].isupper():
                return f'{w} Plan'
        return None

    def _extract_weeks_count(self, text: str) -> int | None:
        m = re.search(r'(\d+)\s+weeks?', text.lower())
        return int(m.group(1)) if m else None

    def _safe_name(self, value: str) -> str:
        return re.sub(r'[^A-Za-z0-9_-]+', '_', value).strip('_')[:40] or 'Plan'
''', encoding='utf-8')

# Patch README
readme = root/'README.md'
readme.write_text(readme.read_text()+r'''

## v0.15 Groq-powered plan drafting in chat

The Chat Assistant now uses the Groq/local LLM provider for free-form plan creation requests when `.env` is configured.

Example:

```text
create an 8 week OpenShift plan for beginner interns with weekly projects
```

The assistant drafts the full plan, shows week summaries, then waits for approval before creating the workbook plan.
''', encoding='utf-8')
