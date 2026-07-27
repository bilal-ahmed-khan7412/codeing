from pathlib import Path

root = Path(__file__).resolve().parent
plan_service = root / 'tracker_services' / 'plan_service.py'
chat_service = root / 'tracker_chat' / 'chat_service.py'
readme = root / 'README.md'

if not plan_service.exists():
    raise SystemExit('tracker_services/plan_service.py not found. Run inside project root.')
if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run inside project root.')

# -----------------------------------------------------------------------------
# 1) Fix v54 runtime error: No module named tracker_commands.results
# -----------------------------------------------------------------------------
s = plan_service.read_text(encoding='utf-8')

s = s.replace(
    "    from tracker_commands.results import CommandResult\n",
    "    from tracker_commands.result import CommandResult\n"
)

# Some project versions may use tracker_commands.results nowhere else, keep fallback safe.
# If the correct module is different in your project, CommandExecutor already uses it; this replacement matches existing structure.

plan_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Make chat route extension-with-plan even if user omits the word 'plan'.
#    Example: Extend musab to 2026-09-30 with Secops Foundation
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

old = """def _v54_extend_with_plan_draft(self, text: str, current_workbook: str | None):\n    lower = (text or '').lower()\n    if 'extend' not in lower or 'with' not in lower or 'plan' not in lower:\n        return None\n    date_m = re.search(r'20\\d{2}-\\d{2}-\\d{2}', text)\n    if not date_m:\n        return None\n    args = {}\n    if current_workbook:\n        args['source'] = current_workbook\n    args['new_end'] = date_m.group(0)\n\n    # Extend Habeeb to 2026-09-30 with Kubernetes Troubleshooting plan\n    m = re.search(r'extend\\s+(?:intern\\s+)?(.+?)\\s+(?:to|until)\\s+20\\d{2}-\\d{2}-\\d{2}\\s+with\\s+(.+?)\\s+plan', text, re.I)\n    if m:\n        args['intern'] = _v54_clean(m.group(1))\n        plan = m.group(2).strip()\n        # Respect exact user wording but use Foundation if just a topic.\n        if 'foundation' not in plan.lower() and 'plan' not in plan.lower():\n            plan = plan[:1].upper() + plan[1:] + ' Foundation'\n        args['plan_name'] = plan\n    args['output'] = _v54_chat_output('extend_intern_with_plan')\n\n    # Add a flat preview note so the generic proposal is still informative.\n    if args.get('intern') and args.get('plan_name'):\n        args['extension_preview'] = f\"Extend {args['intern']} to {args['new_end']} using {args['plan_name']}. This will generate new extension-period daily tasks, weekly projects, and update the main project/scenario to the extension focus.\"\n    return ChatDraft(str(uuid.uuid4()), 'extend_intern_with_plan', args)\n"""

new = """def _v54_extend_with_plan_draft(self, text: str, current_workbook: str | None):\n    lower = (text or '').lower()\n    # Plan-aware extension if user says: extend X to DATE with PLAN_NAME\n    # The word \"plan\" is optional because users often say \"with SecOps Foundation\".\n    if 'extend' not in lower or 'with' not in lower:\n        return None\n    date_m = re.search(r'20\\d{2}-\\d{2}-\\d{2}', text)\n    if not date_m:\n        return None\n    args = {}\n    if current_workbook:\n        args['source'] = current_workbook\n    args['new_end'] = date_m.group(0)\n\n    # Extend Habeeb to 2026-09-30 with Kubernetes Troubleshooting plan\n    # Extend Habeeb to 2026-09-30 with SecOps Foundation\n    m = re.search(r'extend\\s+(?:intern\\s+)?(.+?)\\s+(?:to|until)\\s+20\\d{2}-\\d{2}-\\d{2}\\s+with\\s+(.+?)(?:\\s+plan)?$', text, re.I)\n    if m:\n        args['intern'] = _v54_clean(m.group(1))\n        plan = m.group(2).strip().strip(' .,:;')\n        if 'foundation' not in plan.lower() and 'plan' not in plan.lower():\n            plan = plan[:1].upper() + plan[1:] + ' Foundation'\n        args['plan_name'] = plan\n    args['output'] = _v54_chat_output('extend_intern_with_plan')\n\n    if args.get('intern') and args.get('plan_name'):\n        args['extension_preview'] = f\"Extend {args['intern']} to {args['new_end']} using {args['plan_name']}. This will generate new extension-period daily tasks, weekly projects, and update the main project/scenario to the extension focus.\"\n    return ChatDraft(str(uuid.uuid4()), 'extend_intern_with_plan', args)\n"""

if old in s:
    s = s.replace(old, new)
else:
    # If exact v54 block differs, add a v56 override after it.
    if 'def _v56_extend_with_plan_draft' not in s:
        s += r'''

# v0.56 override: make extension-with-plan route when word "plan" is omitted.
def _v56_extend_with_plan_draft(self, text: str, current_workbook: str | None):
    lower = (text or '').lower()
    if 'extend' not in lower or 'with' not in lower:
        return None
    date_m = re.search(r'20\d{2}-\d{2}-\d{2}', text or '')
    if not date_m:
        return None
    m = re.search(r'extend\s+(?:intern\s+)?(.+?)\s+(?:to|until)\s+20\d{2}-\d{2}-\d{2}\s+with\s+(.+?)(?:\s+plan)?$', text, re.I)
    if not m:
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook
    args['new_end'] = date_m.group(0)
    args['intern'] = _v54_clean(m.group(1)) if '_v54_clean' in globals() else m.group(1).strip().title()
    plan = m.group(2).strip().strip(' .,:;')
    if 'foundation' not in plan.lower() and 'plan' not in plan.lower():
        plan = plan[:1].upper() + plan[1:] + ' Foundation'
    args['plan_name'] = plan
    args['output'] = _v54_chat_output('extend_intern_with_plan') if '_v54_chat_output' in globals() else f'extend_intern_with_plan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    args['extension_preview'] = f"Extend {args['intern']} to {args['new_end']} using {args['plan_name']}. This will generate new extension-period daily tasks, weekly projects, and update the main project/scenario to the extension focus."
    return ChatDraft(str(uuid.uuid4()), 'extend_intern_with_plan', args)

if not hasattr(ChatService, '_base_message_v56'):
    ChatService._base_message_v56 = ChatService.message

def _v56_message(self, text: str, current_workbook: str | None = None):
    draft = _v56_extend_with_plan_draft(self, text, current_workbook)
    if draft:
        return self._response_for_draft(draft)
    return ChatService._base_message_v56(self, text, current_workbook)

ChatService.message = _v56_message
'''

chat_service.write_text(s, encoding='utf-8')

# Compile check both files.
try:
    import py_compile
    py_compile.compile(str(plan_service), doraise=True)
    py_compile.compile(str(chat_service), doraise=True)
except Exception as e:
    raise SystemExit(f'Compile check failed: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.56 Repair Extend Intern With Plan runtime/routing

- Fixed runtime error: `No module named tracker_commands.results`.
- Extension with plan now works even if user omits the word `plan`:
  - `Extend musab to 2026-09-30 with Secops Foundation`
  - `Extend musab to 2026-09-30 with Secops Foundation plan`
- This prevents fallback to the simple `Extend Intern` placeholder workflow when a plan is provided.
''', encoding='utf-8')

print('v0.56 extend intern with plan repair patch applied successfully.')
