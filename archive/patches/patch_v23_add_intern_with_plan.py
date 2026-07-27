from pathlib import Path
import re

root = Path(__file__).resolve().parent
plan_service = root / 'tracker_services' / 'plan_service.py'
registry = root / 'tracker_commands' / 'registry.py'
executor = root / 'tracker_commands' / 'executor.py'
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'

for p in [plan_service, registry, executor, chat_service]:
    if not p.exists():
        raise SystemExit(f'{p} not found. Run this patch inside intern_tracker_system_v0 after v0.22.')

# -----------------------------------------------------------------------------
# 1) PlanService: add add_intern_with_plan workflow
# -----------------------------------------------------------------------------
s = plan_service.read_text(encoding='utf-8')

# Add InternSheetData import if missing.
if 'InternSheetData' not in s.split('\n', 5)[0:5] and 'from tracker_excel.renderer.parser import parse_workbook, PlanSheetData' in s:
    s = s.replace('from tracker_excel.renderer.parser import parse_workbook, PlanSheetData', 'from tracker_excel.renderer.parser import parse_workbook, PlanSheetData, InternSheetData')
elif 'InternSheetData' not in s:
    s = s.replace('from tracker_excel.renderer.parser import parse_workbook', 'from tracker_excel.renderer.parser import parse_workbook, InternSheetData')

if 'def add_intern_with_plan' not in s:
    method = r'''
    def add_intern_with_plan(self, source_path: str, name: str, start_date: str, end_date: str, plan_name: str, output_path: str | None = None, manager: str = '', skip_manager: str = '', final_project: str = '', main_title: str = '', objective: str = '', tech_stack: str = '', scenario: str = '', skills: str = '', deliverable: str = '') -> CommandResult:
        """Create an intern and apply a selected plan in one approved workflow.

        This is intended for chatbot flow:
        Add intern + select plan + preview + approve -> one output workbook.
        """
        name = (name or '').strip()
        plan_name = (plan_name or '').strip()
        if not name or not start_date or not end_date or not plan_name:
            return CommandResult(False, 'name, start_date, end_date, and plan_name are required')
        data = parse_workbook(source_path)
        if any(i.name.strip().lower() == name.lower() for i in data.interns):
            return CommandResult(False, f'Intern already exists: {name}')
        plan = self._find_plan(data, plan_name)
        if not plan:
            return CommandResult(False, f'Plan not found: {plan_name}')
        try:
            start = datetime.fromisoformat(str(start_date))
            end = datetime.fromisoformat(str(end_date))
        except Exception:
            return CommandResult(False, 'start_date and end_date must be valid ISO dates, e.g. 2026-08-01')
        if end.date() < start.date():
            return CommandResult(False, 'end_date cannot be before start_date')

        tasks, weekly_reports, projects = self._build_schedule_from_plan(plan, start, end)
        defaults = self._topic_defaults(plan_name)
        main_title = main_title or defaults['project_title']
        objective = objective or defaults['objective']
        tech_stack = tech_stack or defaults['tech_stack']
        scenario = scenario or defaults['scenario']
        skills = skills or defaults['skills']
        deliverable = deliverable or defaults['deliverable']
        final_project = final_project or main_title

        title = f"Intern Tracker — {name}    ({plan_name})"
        subtitle = f"Start: {start.strftime('%a, %d %b %Y')}    |    End: {end.strftime('%a, %d %b %Y')}    |    Final project: {final_project}"
        intern = InternSheetData(
            name=name,
            title=title,
            subtitle=subtitle,
            main_headers=['Project Title','Objective','Tech Stack','Start','Target End','Status'],
            main_row=[main_title, objective, tech_stack, start, end, 'Pending'],
            scenario_headers=['Scenario','Skills Applied','Deliverable','Assigned Week','Due Date','Status'],
            scenario_row=[scenario, skills, deliverable, max(1, min(6, len(weekly_reports) or 1)), end, 'Pending'],
            task_headers=['Date','Week','Theme','Task Description','Status (Pending/In Progress/Completed)','Remarks'],
            tasks=tasks,
            weekly_headers=['Week #','Theme','Highlights','Blockers','Tasks Completed','Manager Comments','Email Sent','Line Manager Acknowledged'],
            weekly_reports=weekly_reports,
            project_title='SMALL PROJECTS / TASKS',
            project_headers=['#','Title','Description','Assigned Date','Due Date','Status'],
            projects=projects,
        )
        data.interns.append(intern)
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f'Added intern {name} with plan {plan_name}: {out}', out)

'''
    marker = '    def create_plan_from_draft'
    if marker not in s:
        marker = '    def create_plan('
    if marker not in s:
        raise SystemExit('Could not find insertion point in plan_service.py')
    s = s.replace(marker, method + marker)

plan_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Registry and Executor
# -----------------------------------------------------------------------------
s = registry.read_text(encoding='utf-8')
if '"add_intern_with_plan"' not in s:
    s = s.replace('COMMAND_SCHEMAS = {\n', 'COMMAND_SCHEMAS = {\n    "add_intern_with_plan": {"required": ["source", "name", "start_date", "end_date", "plan_name", "output"], "optional": ["manager", "skip_manager", "final_project", "main_title", "objective", "tech_stack", "scenario", "skills", "deliverable"], "description": "Add an intern and apply a selected plan in one approved workflow."},\n')
registry.write_text(s, encoding='utf-8')

s = executor.read_text(encoding='utf-8')
if 'command == "add_intern_with_plan"' not in s:
    s = s.replace('        if command == "create_plan_from_draft":\n', '        if command == "add_intern_with_plan":\n            return self.plan_service.add_intern_with_plan(args["source"], args["name"], args["start_date"], args["end_date"], args["plan_name"], args.get("output"), args.get("manager", ""), args.get("skip_manager", ""), args.get("final_project", ""), args.get("main_title", ""), args.get("objective", ""), args.get("tech_stack", ""), args.get("scenario", ""), args.get("skills", ""), args.get("deliverable", ""))\n        if command == "create_plan_from_draft":\n')
executor.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) ChatService: route add intern with plan prompts to combined workflow
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

if "'add_intern_with_plan': 'Add Intern With Plan'" not in s:
    s = s.replace("'add_intern_basic': 'Add Intern (Form)',", "'add_intern_basic': 'Add Intern (Form)',\n    'add_intern_with_plan': 'Add Intern With Plan',")
if "'add_intern_with_plan': ['source', 'name', 'start_date', 'end_date', 'plan_name', 'output']" not in s:
    s = s.replace("'add_intern_basic': ['source', 'name', 'start_date', 'end_date', 'output'],", "'add_intern_basic': ['source', 'name', 'start_date', 'end_date', 'output'],\n    'add_intern_with_plan': ['source', 'name', 'start_date', 'end_date', 'plan_name', 'output'],")

# Detect add intern with plan before add_intern_basic.
old = """        if 'json' in lower and 'intern' in lower: return 'add_intern'\n        if 'add intern' in lower or 'create intern' in lower: return 'add_intern_basic'\n"""
new = """        if 'json' in lower and 'intern' in lower: return 'add_intern'\n        if ('add intern' in lower or 'create intern' in lower) and ('plan' in lower or 'with ' in lower or 'for ' in lower): return 'add_intern_with_plan'\n        if 'add intern' in lower or 'create intern' in lower: return 'add_intern_basic'\n"""
if old in s:
    s = s.replace(old, new)

# Patch _extract_common for add_intern_with_plan.
old = """        if command == 'add_intern_basic':\n            if len(dates) >= 1: args['start_date'] = dates[0]\n            if len(dates) >= 2: args['end_date'] = dates[1]\n"""
new = """        if command in ['add_intern_basic','add_intern_with_plan']:\n            if len(dates) >= 1: args['start_date'] = dates[0]\n            if len(dates) >= 2: args['end_date'] = dates[1]\n"""
if old in s:
    s = s.replace(old, new)

old = """        if command == 'add_intern_basic':\n            m2 = re.search(r'(?:named|name|intern)\\s+([A-Z][A-Za-z]+(?:\\s+[A-Z][A-Za-z]+){0,3})', text)\n            if m2: args['name'] = m2.group(1).strip()\n"""
new = """        if command in ['add_intern_basic','add_intern_with_plan']:\n            m2 = re.search(r'(?:named|name|intern)\\s+([A-Z][A-Za-z]+(?:\\s+[A-Z][A-Za-z]+){0,3})', text)\n            if m2: args['name'] = m2.group(1).strip()\n            if command == 'add_intern_with_plan':\n                pm = re.search(r'(?:with|for|plan)\\s+([A-Za-z0-9 ._+-]+?)(?:\\s+plan)?(?:\\s+from|\\s+starting|$)', text, re.I)\n                if pm:\n                    val = pm.group(1).strip().rstrip('.')\n                    if val and val.lower() not in ['intern']:\n                        if 'security' in val.lower() or 'infosec' in val.lower() or 'cyber' in val.lower():\n                            args['plan_name'] = 'Information Security Foundation'\n                        elif 'openshift' in val.lower():\n                            args['plan_name'] = 'OpenShift Foundation'\n                        else:\n                            args['plan_name'] = val\n"""
if old in s:
    s = s.replace(old, new)

# Patch fill_from_text add intern field fill if method exists.
if 'elif draft.command == \'apply_plan_to_intern\':' in s and "draft.command == 'add_intern_with_plan'" not in s:
    old = """        if draft.command == 'add_intern_basic':\n            if 'name' not in args or not args.get('name'):\n                m = re.search(r'(?:intern name is|name is|named)\\s+([A-Z][A-Za-z]+(?:\\s+[A-Z][A-Za-z]+){0,3})', text)\n                if m: args['name'] = m.group(1).strip()\n            if dates:\n                args.setdefault('start_date', dates[0])\n                if len(dates) > 1: args.setdefault('end_date', dates[1])\n        elif draft.command == 'apply_plan_to_intern':\n"""
    new = """        if draft.command in ['add_intern_basic','add_intern_with_plan']:\n            if 'name' not in args or not args.get('name'):\n                m = re.search(r'(?:intern name is|name is|named|intern)\\s+([A-Z][A-Za-z]+(?:\\s+[A-Z][A-Za-z]+){0,3})', text)\n                if m: args['name'] = m.group(1).strip()\n            if dates:\n                args.setdefault('start_date', dates[0])\n                if len(dates) > 1: args.setdefault('end_date', dates[1])\n            if draft.command == 'add_intern_with_plan':\n                pm = re.search(r'(?:plan name is|plan is|with|for)\\s+([A-Za-z0-9 ._+-]+)', text, re.I)\n                if pm:\n                    val = pm.group(1).strip().rstrip('.')\n                    if 'security' in val.lower() or 'infosec' in val.lower() or 'cyber' in val.lower(): val = 'Information Security Foundation'\n                    elif 'openshift' in val.lower(): val = 'OpenShift Foundation'\n                    args['plan_name'] = val\n        elif draft.command == 'apply_plan_to_intern':\n"""
    if old in s:
        s = s.replace(old, new)

# Defaults output friendly.
old = """        if command == 'create_workbook': args.setdefault('output', f'Blank_Intern_Tracker_{stamp}.xlsx')\n        elif command != 'summary': args.setdefault('output', f'{command}_{stamp}.xlsx')\n"""
new = """        if command == 'create_workbook': args.setdefault('output', f'Blank_Intern_Tracker_{stamp}.xlsx')\n        elif command == 'add_intern_with_plan': args.setdefault('output', f'Intern_With_Plan_{stamp}.xlsx')\n        elif command != 'summary': args.setdefault('output', f'{command}_{stamp}.xlsx')\n"""
if old in s:
    s = s.replace(old, new)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 4) Chat UI human summary for combined workflow
# -----------------------------------------------------------------------------
if chat_html.exists():
    hs = chat_html.read_text(encoding='utf-8')
    if "cmd === 'add_intern_with_plan'" not in hs:
        hs = hs.replace("if(cmd === 'add_intern_basic') return `I can add ${args.name || 'the intern'} from ${args.start_date || 'start date'} to ${args.end_date || 'end date'}.`;", "if(cmd === 'add_intern_basic') return `I can add ${args.name || 'the intern'} from ${args.start_date || 'start date'} to ${args.end_date || 'end date'}.`;\n  if(cmd === 'add_intern_with_plan') return `I can add ${args.name || 'the intern'} from ${args.start_date || 'start date'} to ${args.end_date || 'end date'}, apply ${args.plan_name || 'the selected plan'}, and create related project/scenario details.`;")
    chat_html.write_text(hs, encoding='utf-8')

# -----------------------------------------------------------------------------
# 5) README note
# -----------------------------------------------------------------------------
readme = root / 'README.md'
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.23 Add Intern With Plan workflow

- Added combined workflow command `add_intern_with_plan`.
- Chat prompts like `add intern Hakeel from 2026-08-01 to 2026-09-30 with Information Security Foundation plan` now create one proposal that:
  - adds the intern,
  - applies the selected plan using the intern's start/end dates,
  - fills main project/capstone defaults,
  - fills real-world scenario defaults,
  - refreshes dashboard.
- Workbook is only created after approval.
''', encoding='utf-8')

print('v0.23 add intern with plan workflow patch applied successfully.')
