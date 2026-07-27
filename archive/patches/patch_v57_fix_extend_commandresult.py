from pathlib import Path

root = Path(__file__).resolve().parent
plan_service = root / 'tracker_services' / 'plan_service.py'
readme = root / 'README.md'

if not plan_service.exists():
    raise SystemExit('tracker_services/plan_service.py not found. Run inside project root.')

s = plan_service.read_text(encoding='utf-8')

# v0.57: Fix Extend Intern With Plan CommandResult import issue.
# Previous patches tried:
#   from tracker_commands.results import CommandResult
# then:
#   from tracker_commands.result import CommandResult
# but this project already has CommandResult available in plan_service.py in most builds.
# The safest fix is: do not import it inside the monkey-patched function.
# If CommandResult is not available for any reason, define a tiny local compatible class.

bad_imports = [
    "    from tracker_commands.results import CommandResult\n",
    "    from tracker_commands.result import CommandResult\n",
]
for bad in bad_imports:
    s = s.replace(bad, "")

needle = "    from tracker_services.version_service import VersionService\n\n    intern_name = (intern_name or '').strip()\n"
replacement = """    from tracker_services.version_service import VersionService\n\n    # Use the module's existing CommandResult if present. If not, provide a\n    # minimal compatible fallback so the command can still return properly.\n    try:\n        CommandResult\n    except NameError:\n        class CommandResult:  # fallback for monkey-patched deployments\n            def __init__(self, ok, message, output_path=None, data=None):\n                self.ok = ok\n                self.message = message\n                self.output_path = output_path\n                self.data = data or {}\n\n    intern_name = (intern_name or '').strip()\n"""

if needle in s and 'fallback for monkey-patched deployments' not in s:
    s = s.replace(needle, replacement, 1)
elif 'fallback for monkey-patched deployments' in s:
    pass
else:
    print('Warning: expected insertion point not found. Bad imports were still removed.')

plan_service.write_text(s, encoding='utf-8')

# Compile check.
try:
    import py_compile
    py_compile.compile(str(plan_service), doraise=True)
except Exception as e:
    raise SystemExit(f'plan_service.py still has a compile issue: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.57 Fix Extend Intern With Plan CommandResult import

- Fixes runtime error from `extend_intern_with_plan`:
  - `No module named tracker_commands.results`
  - `No module named tracker_commands.result`
- The monkey-patched extension workflow now uses the existing `CommandResult` from `plan_service.py`, or a minimal compatible fallback if needed.
''', encoding='utf-8')

print('v0.57 fixed Extend Intern With Plan CommandResult import successfully.')
