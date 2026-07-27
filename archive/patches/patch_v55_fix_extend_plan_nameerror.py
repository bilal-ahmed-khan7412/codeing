from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = chat_service.read_text(encoding='utf-8')

# v0.55: Repair v0.54 import failure.
# The v0.54 patch wrote LABELS[...] and REQUIRED[...] as module-level globals,
# but this codebase does not define LABELS/REQUIRED at module import time.
# That causes: NameError: name 'LABELS' is not defined.
# Remove those two module-level assignments. The command still works because the
# v54 chat override creates a complete ChatDraft with all required args.

s = s.replace("LABELS['extend_intern_with_plan'] = 'Extend Intern With Plan'\n", "# v0.55 removed invalid LABELS global assignment for extend_intern_with_plan\n")
s = s.replace("REQUIRED['extend_intern_with_plan'] = ['source', 'intern', 'new_end', 'plan_name', 'output']\n", "# v0.55 removed invalid REQUIRED global assignment for extend_intern_with_plan\n")

# If the previous broken lines were inserted with double quotes for any reason,
# remove those variations too.
s = s.replace('LABELS["extend_intern_with_plan"] = "Extend Intern With Plan"\n', '# v0.55 removed invalid LABELS global assignment for extend_intern_with_plan\n')
s = s.replace('REQUIRED["extend_intern_with_plan"] = ["source", "intern", "new_end", "plan_name", "output"]\n', '# v0.55 removed invalid REQUIRED global assignment for extend_intern_with_plan\n')

# Make the label look nice in proposal text if the UI/chat service falls back to
# raw command names and a label helper is not available.
if 'extend_intern_with_plan' in s and 'Extend Intern With Plan' not in s:
    s += "\n# v0.55 note: extend_intern_with_plan label is handled by proposal/UI fallback.\n"

chat_service.write_text(s, encoding='utf-8')

# Compile check for the edited chat_service.py.
try:
    import py_compile
    py_compile.compile(str(chat_service), doraise=True)
except Exception as e:
    raise SystemExit(f'chat_service.py still has a syntax/import compile issue: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.55 Fix Extend Intern With Plan NameError

- Fixed server startup crash from v0.54:
  `NameError: name 'LABELS' is not defined`.
- Removed invalid module-level `LABELS[...]` and `REQUIRED[...]` assignments.
- `extend_intern_with_plan` chat override remains available for full prompts like:
  `Extend Habeeb to 2026-09-30 with Kubernetes Troubleshooting plan`.
''', encoding='utf-8')

print('v0.55 extend intern with plan NameError fix applied successfully.')
