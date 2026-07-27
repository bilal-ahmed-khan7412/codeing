from pathlib import Path
import re

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# v0.52: Strip leading duration tokens from extracted plan names.
# Fixes: "add plan 8 weeks Devops" -> "DevOps Foundation"
# instead of "8 DevOps Foundation".

# Patch _clean_plan_name_candidate to remove leading numbers/duration more aggressively.
start = s.find('    def _clean_plan_name_candidate')
if start == -1:
    raise SystemExit('Could not find _clean_plan_name_candidate in chat_service.py. Apply plan-name priority patches first.')
end = s.find('\n    def ', start + 5)
segment = s[start:end if end != -1 else len(s)]

# Insert duration cleanup after value is stripped.
needle = "        value = (value or '').strip().rstrip('.')\n"
insert = """        value = (value or '').strip().rstrip('.')\n        # Remove leading duration tokens accidentally captured as part of the plan name.\n        # Examples: \"8 Devops\", \"8 weeks Devops\", \"eight weeks AI Engineering\".\n        value = re.sub(r'^(?:\\d+|one|two|three|four|five|six|seven|eight|nine|ten)\\s*-?\\s*(?:week|weeks)?\\s+', '', value, flags=re.I).strip()\n"""
if needle in segment and 'Remove leading duration tokens accidentally captured' not in segment:
    segment = segment.replace(needle, insert, 1)
else:
    print('Duration cleanup already present or expected insertion point not found.')

# Add DevOps/AI aliases if aliases dict present.
if 'aliases = {' in segment and "'devops': 'DevOps Foundation'" not in segment:
    segment = segment.replace("aliases = {", "aliases = {\n            'devops': 'DevOps Foundation',\n            'devopsfoundation': 'DevOps Foundation',\n            'aiengineering': 'AI Engineering Foundation',\n            'aiengineeringfoundation': 'AI Engineering Foundation',")

s = s[:start] + segment + (s[end:] if end != -1 else '')

# Also patch explicit-plan regex order by ensuring "plan 8 weeks X" pattern is checked before "plan X 8 weeks".
# If both patterns exist, no destructive replacement needed, because cleaner now strips the leading 8.

chat_service.write_text(s, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.52 Strip duration from plan names

- Fixes prompts like `add plan 8 weeks Devops` creating `8 DevOps Foundation`.
- Plan names now remove leading duration tokens, so the result becomes `DevOps Foundation`.
- Also improves aliases for DevOps and AI Engineering.
''', encoding='utf-8')

print('v0.52 strip duration from plan name patch applied successfully.')
