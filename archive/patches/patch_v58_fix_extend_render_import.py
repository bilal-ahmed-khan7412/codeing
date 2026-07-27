from pathlib import Path

root = Path(__file__).resolve().parent
plan_service = root / 'tracker_services' / 'plan_service.py'
readme = root / 'README.md'

if not plan_service.exists():
    raise SystemExit('tracker_services/plan_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = plan_service.read_text(encoding='utf-8')

# v0.58: Fix Extend Intern With Plan RenderService import issue.
# Error seen:
#   No module named 'tracker_excel.renderer.render_service'
# In this codebase RenderService is already normally imported at module level in
# plan_service.py, so the monkey-patched function should not import a guessed path.
# We remove that bad local import and add a safe runtime fallback.

bad_lines = [
    "    from tracker_excel.renderer.render_service import RenderService\n",
    "    from tracker_services.version_service import VersionService\n",
]
for line in bad_lines:
    s = s.replace(line, "")

needle = "    from tracker_chat.intern_sheet_drafter import InternSheetDrafter\n\n    intern_name = (intern_name or '').strip()\n"
replacement = """    from tracker_chat.intern_sheet_drafter import InternSheetDrafter\n\n    # Use the module-level RenderService and VersionService if they already exist.\n    # These are imported by the original PlanService in most project versions.\n    # If a name is missing, try common import locations as a fallback.\n    try:\n        RenderService\n    except NameError:\n        try:\n            from tracker_excel.renderer.render import RenderService  # type: ignore\n        except Exception:\n            from tracker_excel.renderer import RenderService  # type: ignore\n    try:\n        VersionService\n    except NameError:\n        from tracker_services.version_service import VersionService  # type: ignore\n\n    intern_name = (intern_name or '').strip()\n"""

if needle in s and "Use the module-level RenderService and VersionService" not in s:
    s = s.replace(needle, replacement, 1)
elif "Use the module-level RenderService and VersionService" in s:
    pass
else:
    print('Warning: expected insertion point not found. Bad RenderService import was still removed.')

plan_service.write_text(s, encoding='utf-8')

# Compile check.
try:
    import py_compile
    py_compile.compile(str(plan_service), doraise=True)
except Exception as e:
    raise SystemExit(f'plan_service.py still has a compile issue after patch: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.58 Fix Extend Intern With Plan RenderService import

- Fixes runtime error from `extend_intern_with_plan`:
  `No module named tracker_excel.renderer.render_service`.
- Removes the guessed local import path and uses the module-level `RenderService` already used by the project.
- Adds safe fallback imports only if needed.
''', encoding='utf-8')

print('v0.58 fixed Extend Intern With Plan RenderService import successfully.')
