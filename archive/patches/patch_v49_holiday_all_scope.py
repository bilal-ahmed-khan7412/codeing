from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
executor = root / 'tracker_commands' / 'executor.py'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# -----------------------------------------------------------------------------
# v0.49 Add Holiday scope normalization
# Fixes prompts like:
#   add holidat for all interns date 2026-07-16
# which were interpreted with an invalid/non-matching scope and failed with:
#   No interns matched the holiday scope
# -----------------------------------------------------------------------------

# Helper for holiday normalization.
if 'def _normalize_holiday_args_v49' not in s:
    helper = r'''
    def _normalize_holiday_args_v49(self, text: str, args: dict):
        lower = (text or '').lower()
        # Global/all interns holiday should apply to all intern schedules.
        if any(x in lower for x in ['all interns', 'everyone', 'global', 'company-wide', 'company wide', 'all users']):
            args['scope'] = 'global'
            args.pop('intern_name', None)
        # If a single intern is explicitly mentioned, keep individual scope.
        m = re.search(r'(?:for intern|for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})', text or '')
        if m and 'all interns' not in lower:
            args['scope'] = 'intern'
            args['intern_name'] = m.group(1).strip()
        # Default no explicit scope to global because holidays are usually calendar-wide.
        args.setdefault('scope', 'global')
        args.setdefault('name', 'Holiday')

'''
    marker = '    def _build_rule_draft(self, text: str, current_workbook: str | None) -> ChatDraft:'
    if marker not in s:
        raise SystemExit('Could not find _build_rule_draft insertion point in chat_service.py')
    s = s.replace(marker, helper + marker)

# Normalize rule-built add_holiday drafts before response.
old = """        self._extract_common(text, lower, command, args)\n        self._defaults(command, args)\n        return ChatDraft(str(uuid.uuid4()), command, args)\n"""
new = """        self._extract_common(text, lower, command, args)\n        self._defaults(command, args)\n        if command == 'add_holiday':\n            self._normalize_holiday_args_v49(text, args)\n        return ChatDraft(str(uuid.uuid4()), command, args)\n"""
if old in s:
    s = s.replace(old, new)

# Normalize LLM-built add_holiday drafts too.
old = """        self._defaults(command, args)\n        return ChatDraft(str(uuid.uuid4()), command, args)\n"""
new = """        self._defaults(command, args)\n        if command == 'add_holiday':\n            self._normalize_holiday_args_v49(text, args)\n        return ChatDraft(str(uuid.uuid4()), command, args)\n"""
# Replace first remaining occurrence in _build_llm_intent_draft only if not already normalized nearby.
idx = s.find('    def _build_llm_intent_draft')
if idx != -1:
    sub_end = s.find('    def _build_rule_draft', idx)
    sub = s[idx:sub_end if sub_end != -1 else len(s)]
    if "if command == 'add_holiday'" not in sub and old in sub:
        sub = sub.replace(old, new, 1)
        s = s[:idx] + sub + (s[sub_end:] if sub_end != -1 else '')

# Make detector tolerate common typo "holidat" explicitly.
s = s.replace("if 'holiday' in lower: return 'add_holiday'", "if 'holiday' in lower or 'holidat' in lower: return 'add_holiday'")

chat_service.write_text(s, encoding='utf-8')

# Also harden executor side if possible: normalize add_holiday scope right before execution.
if executor.exists():
    ex = executor.read_text(encoding='utf-8')
    if 'def _normalize_holiday_args_v49_executor' not in ex:
        ex = ex.replace('class CommandExecutor:', r'''
def _normalize_holiday_args_v49_executor(args: dict):
    scope = str(args.get('scope') or '').strip().lower()
    intern_name = str(args.get('intern_name') or '').strip()
    if scope in {'all', 'all interns', 'everyone', 'global', 'company-wide', 'company wide', ''}:
        args['scope'] = 'global'
        args.pop('intern_name', None)
    elif intern_name:
        args['scope'] = 'intern'
    else:
        args['scope'] = 'global'

class CommandExecutor:''')
    # Insert normalization inside execute before command routing.
    if "_normalize_holiday_args_v49_executor(args)" not in ex:
        ex = ex.replace("        command = payload.get(\"command\")\n        args = payload.get(\"args\") or {}",
                        "        command = payload.get(\"command\")\n        args = payload.get(\"args\") or {}\n        if command == 'add_holiday':\n            _normalize_holiday_args_v49_executor(args)")
    executor.write_text(ex, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.49 Add Holiday all-interns scope fix

- `add holiday for all interns date 2026-07-16` now normalizes to `scope=global`.
- Common typo `holidat` is recognized as holiday.
- Executor also normalizes holiday scope before execution to avoid `No interns matched the holiday scope` for all-intern holidays.
''', encoding='utf-8')

print('v0.49 holiday all-interns scope patch applied successfully.')
