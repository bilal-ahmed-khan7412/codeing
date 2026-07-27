from pathlib import Path
import re

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
index = root / 'web' / 'index.html'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

for p in [chat_service, index]:
    if not p.exists():
        raise SystemExit(f'{p} not found. Run this patch inside intern_tracker_system_v0 after v0.23/v0.24.')

# -----------------------------------------------------------------------------
# 1) Chat routing: normal "add intern" should require a plan and use add_intern_with_plan.
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

# Replace add intern detection so add intern always routes to add_intern_with_plan.
s = s.replace(
"""        if 'json' in lower and 'intern' in lower: return 'add_intern'\n        if ('add intern' in lower or 'create intern' in lower or 'new intern' in lower) and ('plan' in lower or 'with ' in lower or 'for ' in lower): return 'add_intern_with_plan'\n        if 'add intern' in lower or 'create intern' in lower: return 'add_intern_basic'\n""",
"""        if 'json' in lower and 'intern' in lower: return 'add_intern'\n        # User-facing intern creation should always be plan-based.\n        # If plan_name is missing, the draft asks for it instead of creating placeholders.\n        if 'add intern' in lower or 'create intern' in lower or 'new intern' in lower: return 'add_intern_with_plan'\n"""
)

# Also patch older exact variant if present.
s = s.replace(
"""        if 'json' in lower and 'intern' in lower: return 'add_intern'\n        if ('add intern' in lower or 'create intern' in lower) and ('plan' in lower or 'with ' in lower or 'for ' in lower): return 'add_intern_with_plan'\n        if 'add intern' in lower or 'create intern' in lower: return 'add_intern_basic'\n""",
"""        if 'json' in lower and 'intern' in lower: return 'add_intern'\n        if 'add intern' in lower or 'create intern' in lower or 'new intern' in lower: return 'add_intern_with_plan'\n"""
)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Forms page: hide Add Intern (Form) and Apply Plan to Intern; add Add Intern With Plan.
# -----------------------------------------------------------------------------
s = index.read_text(encoding='utf-8')

# Add command if absent. Use mutation after commands array is created, before fieldHtml.
if "id:'add_intern_with_plan'" not in s:
    inject = r'''
// User-facing intern creation should be plan-based.
commands.unshift({ id:'add_intern_with_plan', title:'Add Intern With Plan', fields:[['source','Source workbook','Tracker_With_Plan.xlsx'], ['name','Intern name','Hakeel'], ['start_date','Start date YYYY-MM-DD','2026-08-01'], ['end_date','End date YYYY-MM-DD','2026-09-30'], ['plan_name','Plan name','Information Security Foundation'], ['manager','Manager',''], ['skip_manager','Skip manager',''], ['final_project','Final project optional',''], ['output','Output file','Intern_With_Plan.xlsx']] });
'''
    marker = "function fieldHtml(cmd, f) {"
    if marker not in s:
        raise SystemExit('Could not find fieldHtml marker in web/index.html')
    s = s.replace(marker, inject + "\n" + marker)

# Filter out old user-facing intern creation/apply-plan controls after add command is inserted.
if "commands = commands.filter" not in s and "const commands = [" in s:
    # Commands is const, cannot reassign. Mutate array in place.
    filter_code = """
// Hide older separate intern flow from the user-facing forms.
for (let i = commands.length - 1; i >= 0; i--) { if (['add_intern_basic','apply_plan_to_intern'].includes(commands[i].id)) commands.splice(i, 1); }
"""
    marker = "function fieldHtml(cmd, f) {"
    s = s.replace(marker, filter_code + "\n" + marker)

# Update heading link text if desired.
s = s.replace('Open Chat Assistant', 'Open Chat Assistant')
index.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Chat examples: prefer Add Intern With Plan and remove Apply Plan example.
# -----------------------------------------------------------------------------
if chat_html.exists():
    hs = chat_html.read_text(encoding='utf-8')
    hs = hs.replace("useExample('add intern named Musab Khan from 2026-08-01 to 2026-09-30')", "useExample('add intern Musab Khan from 2026-08-01 to 2026-09-30 with Information Security Foundation plan')")
    hs = hs.replace('Add intern</button>', 'Add intern with plan</button>')
    # Remove apply plan example button if exact line exists.
    hs = re.sub(r'\n\s*<button class="example" onclick="useExample\(\'apply plan OpenShift Foundation to intern Musab Khan\'\)">Apply plan to intern</button>', '', hs)
    chat_html.write_text(hs, encoding='utf-8')

# -----------------------------------------------------------------------------
# 4) README note.
# -----------------------------------------------------------------------------
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.25 Add Intern With Plan only UX

- User-facing intern creation now uses `Add Intern With Plan`.
- The old separate `Add Intern (Form)` and `Apply Plan to Intern` controls are hidden from the forms UI.
- In chat, `add intern ...` now routes to `Add Intern With Plan` and asks for `plan_name` if missing.
- Backend commands are kept for compatibility, but the normal UI flow is now plan-based intern creation.
''', encoding='utf-8')

print('v0.25 Add Intern With Plan only UX patch applied successfully.')
