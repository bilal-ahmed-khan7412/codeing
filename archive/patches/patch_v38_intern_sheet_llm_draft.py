from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_dir = root / 'tracker_chat'
plan_service = root / 'tracker_services' / 'plan_service.py'
executor = root / 'tracker_commands' / 'executor.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

for p in [chat_service, plan_service, executor, chat_html]:
    if not p.exists():
        raise SystemExit(f'{p} not found. Run this patch inside intern_tracker_system_v0 after v0.23+ chat/workflow patches.')
chat_dir.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# 1) Add a real intern-sheet drafter: use plan as context, not as literal final output.
# -----------------------------------------------------------------------------
(chat_dir / 'intern_sheet_drafter.py').write_text(r'''
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import re

try:
    from tracker_config.settings import load_settings
    from tracker_llm.providers import build_provider
except Exception:
    load_settings = None
    build_provider = None

from tracker_excel.renderer.parser import parse_workbook

BASE_DIR = Path(__file__).resolve().parents[1]


def resolve_workbook_path(value: str) -> str:
    """Resolve a workbook label from chat into a real local path."""
    if not value:
        return value
    p = Path(value)
    if p.exists():
        return str(p)
    for folder in [BASE_DIR / 'outputs', BASE_DIR / 'uploads', BASE_DIR]:
        candidate = folder / Path(value).name
        if candidate.exists():
            return str(candidate)
    return value


def clean_debug_text(value, default=''):
    text = str(value or '').strip()
    low = text.lower()
    debug = ['llm returned no detailed weeks', 'generated safe draft', 'adjusted to', 'fallback']
    if any(x in low for x in debug):
        return default
    return text or default


class InternSheetDrafter:
    """Generate a complete intern sheet draft from plan context and dates.

    This is used before approval. It does NOT create the workbook. The approved
    draft is later passed into add_intern_with_plan as schedule_preview.
    """
    def __init__(self, env_path='.env'):
        self.provider = None
        if load_settings and build_provider:
            try:
                settings = load_settings(env_path)
                if settings.ai_provider.lower() != 'mock':
                    self.provider = build_provider(settings)
            except Exception:
                self.provider = None

    def draft(self, source: str, name: str, start_date: str, end_date: str, plan_name: str) -> dict:
        source_path = resolve_workbook_path(source)
        plan_context = self._load_plan_context(source_path, plan_name)
        week_ranges = self._week_ranges(start_date, end_date)
        week_count = len(week_ranges) or 8
        if self.provider:
            llm = self._draft_with_llm(name, start_date, end_date, plan_name, plan_context, week_count)
            if self._is_good_draft(llm, week_count):
                return self._merge_dates(llm, week_ranges)
        return self._fallback_draft(plan_name, week_ranges)

    def _load_plan_context(self, source_path: str, plan_name: str) -> list[dict]:
        try:
            data = parse_workbook(source_path)
            q = (plan_name or '').strip().lower()
            plan = None
            for p in data.plans:
                if q in (p.title or '').lower() or q == (p.sheet_name or '').lower():
                    plan = p
                    break
            if not plan:
                return []
            rows = []
            for row in plan.rows:
                if not row:
                    continue
                try:
                    week = int(row[0])
                except Exception:
                    continue
                rows.append({
                    'week': week,
                    'theme': clean_debug_text(row[1] if len(row) > 1 else '', ''),
                    'task': clean_debug_text(row[2] if len(row) > 2 else '', ''),
                    'weekly_project': clean_debug_text(row[3] if len(row) > 3 else '', ''),
                    'notes': clean_debug_text(row[4] if len(row) > 4 else '', ''),
                })
            return rows
        except Exception:
            return []

    def _week_ranges(self, start_date: str, end_date: str):
        try:
            start = datetime.fromisoformat(str(start_date))
            end = datetime.fromisoformat(str(end_date))
        except Exception:
            return []
        ranges = {}
        current = start
        workday = 0
        while current.date() <= end.date():
            if current.weekday() < 5:
                workday += 1
                week = ((workday - 1) // 5) + 1
                ranges.setdefault(week, []).append(current)
            current += timedelta(days=1)
        return [
            {'week': w, 'date_range': f"{dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}"}
            for w, dates in sorted(ranges.items())
        ]

    def _draft_with_llm(self, name, start_date, end_date, plan_name, plan_context, week_count):
        prompt = f"""
You are drafting a complete intern tracker sheet BEFORE approval.
Use the plan only as context. Do not copy generic fallback wording literally.
Return ONLY JSON. No markdown.

Intern: {name}
Start date: {start_date}
End date: {end_date}
Plan name: {plan_name}
Generated week count from dates: {week_count}
Existing plan rows/context:
{plan_context}

Return this exact JSON shape:
{{
  "main_project": {{
    "title": "...",
    "objective": "...",
    "tech_stack": "..."
  }},
  "scenario": {{
    "scenario": "...",
    "skills": "...",
    "deliverable": "..."
  }},
  "weeks": [
    {{
      "week": 1,
      "theme": "specific week theme",
      "daily_task": "specific daily task focus for that week, detailed and actionable",
      "weekly_project": "specific weekly project/deliverable",
      "notes": "short outcome or validation criteria"
    }}
  ]
}}

Quality rules:
- Create exactly {week_count} week objects.
- Each daily_task must be specific, hands-on, and relevant to {plan_name}.
- Each weekly_project must be a concrete deliverable.
- Never use these phrases: task to be assigned, core concepts, hands-on practice, final demo, foundation and environment setup, LLM returned no detailed weeks, generated safe draft.
- If plan context is generic, improve it into a strong {plan_name} internship plan.
"""
        try:
            data = self.provider.complete_json(prompt)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _is_good_draft(self, data, week_count: int) -> bool:
        if not isinstance(data, dict):
            return False
        weeks = data.get('weeks')
        if not isinstance(weeks, list) or len(weeks) < week_count:
            return False
        bad = ['task to be assigned', 'core concepts', 'hands-on practice', 'final demo', 'foundation and environment setup', 'llm returned no detailed weeks', 'generated safe draft']
        for w in weeks[:week_count]:
            text = ' '.join(str(w.get(k, '')) for k in ['theme', 'daily_task', 'weekly_project', 'notes']).lower()
            if any(x in text for x in bad):
                return False
            if len(str(w.get('daily_task', '')).strip()) < 35 or len(str(w.get('weekly_project', '')).strip()) < 20:
                return False
        return True

    def _merge_dates(self, data: dict, week_ranges: list[dict]) -> dict:
        weeks = data.get('weeks') or []
        merged = []
        for i, wr in enumerate(week_ranges):
            w = weeks[i] if i < len(weeks) and isinstance(weeks[i], dict) else {}
            merged.append({
                'week': wr['week'],
                'date_range': wr['date_range'],
                'theme': clean_debug_text(w.get('theme'), f"Week {wr['week']} Learning"),
                'daily_task': clean_debug_text(w.get('daily_task'), 'Complete assigned practical tasks for this week.'),
                'weekly_project': clean_debug_text(w.get('weekly_project'), f"Week {wr['week']} deliverable"),
                'notes': clean_debug_text(w.get('notes'), ''),
            })
        return {
            'main_project': data.get('main_project') or {},
            'scenario': data.get('scenario') or {},
            'weeks': merged,
        }

    def _fallback_draft(self, plan_name: str, week_ranges: list[dict]) -> dict:
        p = (plan_name or '').lower()
        if 'devops' in p or 'dev ops' in p:
            base = [
                ('Linux Basics and Shell Operations', 'Practice shell navigation, file permissions, process monitoring, service checks, environment variables, and log inspection.', 'Prepare a Linux environment checklist with command outputs and troubleshooting notes.', 'Validate Linux command fluency and environment readiness.'),
                ('Git and GitHub Workflow', 'Practice commits, branches, pull requests, merge conflict resolution, repository hygiene, and release tagging.', 'Build a Git workflow demo repository with branch, PR, and merge documentation.', 'Validate version control workflow understanding.'),
                ('Docker and Containerization', 'Build Docker images, write Dockerfiles, run containers, manage volumes, inspect logs, and use Docker Compose.', 'Containerize a sample application and document build/run steps.', 'Validate container packaging and troubleshooting.'),
                ('Kubernetes Fundamentals', 'Practice pods, deployments, services, namespaces, labels, probes, and basic kubectl troubleshooting.', 'Deploy a sample app on Kubernetes and expose it internally.', 'Validate Kubernetes workload basics.'),
                ('CI/CD Pipeline Basics', 'Create a pipeline that builds, tests, packages, and deploys a sample application with basic quality gates.', 'Build a CI/CD pipeline for a containerized sample app.', 'Validate automated build/deploy workflow.'),
                ('Monitoring and Logging', 'Collect logs, inspect metrics, configure simple health checks, and identify common failure signals.', 'Create a monitoring/logging checklist and troubleshoot a simulated failure.', 'Validate observability workflow.'),
                ('Troubleshooting and Automation', 'Debug deployment failures, automate repetitive checks, write scripts, and document root cause analysis.', 'Create an automation script for deployment validation and failure triage.', 'Validate troubleshooting and automation skills.'),
                ('Final DevOps Deployment Project', 'Combine Linux, Git, Docker, Kubernetes, CI/CD, monitoring, and troubleshooting into one deployment demo.', 'Deliver a working DevOps deployment pipeline demo with final report.', 'Validate end-to-end DevOps readiness.'),
            ]
            main = {
                'title': 'DevOps CI/CD Deployment Pipeline Demo',
                'objective': 'Build, containerize, deploy, monitor, and troubleshoot a sample application using a practical DevOps toolchain.',
                'tech_stack': 'Linux, Git, Docker, Kubernetes, CI/CD, monitoring, logging, automation',
            }
            scenario = {
                'scenario': 'A sample application must be containerized, deployed through a CI/CD pipeline, monitored after deployment, and troubleshot when deployment or runtime issues occur.',
                'skills': 'Linux, Git, Docker, Kubernetes, CI/CD, monitoring, logging, troubleshooting, automation',
                'deliverable': 'Working deployment pipeline, Kubernetes deployment, monitoring/troubleshooting notes, and final demo report.',
            }
        elif 'security' in p or 'infosec' in p or 'cyber' in p or 'secops' in p:
            base = [
                ('Security Foundations and Governance', 'Review CIA, risk basics, security policies, controls, and common security operations roles.', 'Create a security controls checklist for a sample system.', 'Validate foundational security understanding.'),
                ('Networking and Linux Security Logs', 'Analyze ports, protocols, Linux auth logs, permissions, and suspicious activity indicators.', 'Analyze sample Linux authentication logs and identify suspicious entries.', 'Validate log analysis basics.'),
                ('Vulnerability Triage and Risk', 'Review sample vulnerabilities, severity, affected assets, exploitability, and prioritization.', 'Prepare a vulnerability triage report with remediation priorities.', 'Validate risk-based prioritization.'),
                ('Identity and Access Review', 'Assess users, roles, MFA, least privilege, inactive accounts, and access review evidence.', 'Create an IAM access review checklist and remediation notes.', 'Validate identity security workflow.'),
                ('SIEM Alert Investigation', 'Review alerts, correlate events, identify indicators, document findings, and classify incidents.', 'Investigate sample SIEM alerts and write an investigation summary.', 'Validate alert triage.'),
                ('Incident Response Fundamentals', 'Practice triage, containment, evidence capture, timeline creation, communication, and recovery notes.', 'Write a mini incident response report from a simulated alert.', 'Validate IR lifecycle understanding.'),
                ('Cloud and Application Security Basics', 'Review secure configuration, secrets handling, dependency risks, and simple app/cloud controls.', 'Assess a sample app/cloud checklist and recommend fixes.', 'Validate broad security review skills.'),
                ('Final Security Assessment Project', 'Combine log analysis, vulnerability triage, IAM review, and incident response into a final assessment.', 'Deliver a final security assessment report and presentation.', 'Validate end-to-end security readiness.'),
            ]
            main = {
                'title': 'Security Assessment and Incident Triage Demo',
                'objective': 'Review security controls, investigate sample alerts, triage vulnerabilities, and produce remediation recommendations.',
                'tech_stack': 'Linux logs, SIEM concepts, IAM, vulnerability management, incident response, security reporting',
            }
            scenario = {
                'scenario': 'A sample environment has suspicious authentication activity, vulnerable services, and incomplete access controls. The intern must review logs, triage findings, prioritize risk, and recommend remediation steps.',
                'skills': 'Log analysis, SIEM triage, vulnerability assessment, IAM review, incident response, risk reporting',
                'deliverable': 'Security assessment report, incident triage notes, prioritized remediation list, and final presentation.',
            }
        else:
            base = [
                (f'{plan_name} Orientation and Setup', f'Set up tools and complete practical orientation tasks for {plan_name}.', f'Prepare an environment setup report for {plan_name}.', 'Validate setup readiness.'),
                (f'{plan_name} Core Skills', f'Practice the core technical skills required for {plan_name}.', f'Complete a guided {plan_name} lab and summary.', 'Validate core concepts.'),
                (f'{plan_name} Practical Workflow', f'Apply {plan_name} skills in a hands-on workflow.', f'Build a small {plan_name} practical demo.', 'Validate practical application.'),
                (f'{plan_name} Intermediate Tasks', f'Combine multiple {plan_name} tasks into a realistic scenario.', f'Complete an integrated {plan_name} mini-project.', 'Validate integration.'),
                (f'{plan_name} Troubleshooting', f'Debug common {plan_name} issues and document root causes.', f'Prepare a troubleshooting report.', 'Validate troubleshooting.'),
                (f'{plan_name} Automation', f'Automate or repeat common {plan_name} checks and workflows.', f'Create an automation or repeatability checklist.', 'Validate repeatability.'),
                (f'{plan_name} Project Polish', f'Improve documentation, quality, and presentation for {plan_name}.', f'Prepare project documentation and improvements.', 'Validate polish.'),
                (f'Final {plan_name} Project', f'Complete and present a final {plan_name} practical project.', f'Deliver final demo and report.', 'Validate final readiness.'),
            ]
            main = {
                'title': f'{plan_name} Final Practical Demo',
                'objective': f'Complete a practical project aligned with the {plan_name} plan and document the final outcome.',
                'tech_stack': plan_name,
            }
            scenario = {
                'scenario': f'A realistic work scenario aligned with the {plan_name} plan requires the intern to investigate, implement, validate, and document a solution.',
                'skills': plan_name,
                'deliverable': 'Working demo, notes, and final summary report.',
            }
        weeks = []
        for i, wr in enumerate(week_ranges):
            b = base[i % len(base)]
            weeks.append({'week': wr['week'], 'date_range': wr['date_range'], 'theme': b[0], 'daily_task': b[1], 'weekly_project': b[2], 'notes': b[3]})
        return {'main_project': main, 'scenario': scenario, 'weeks': weeks}
''', encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Patch ChatService enrichment by overriding it with LLM intern-sheet drafter.
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')
if 'from tracker_chat.intern_sheet_drafter import InternSheetDrafter' not in s:
    s = s.replace('from tracker_commands.executor import CommandExecutor', 'from tracker_commands.executor import CommandExecutor\nfrom tracker_chat.intern_sheet_drafter import InternSheetDrafter')

if 'self.intern_sheet_drafter = InternSheetDrafter' not in s:
    s = s.replace('self.executor = CommandExecutor()\n', 'self.executor = CommandExecutor()\n        self.intern_sheet_drafter = InternSheetDrafter()\n')

# Append monkey-patch override. This avoids brittle replacement of earlier enrich method versions.
if 'v38 override: LLM intern sheet draft from plan context' not in s:
    s += r'''

# v38 override: LLM intern sheet draft from plan context
# This intentionally overrides older enrichment logic. Add Intern With Plan now uses
# the selected plan as context to produce a complete editable intern-sheet draft.
def _v38_enrich_add_intern_with_plan(self, draft):
    args = draft.args
    required = ['source', 'name', 'start_date', 'end_date', 'plan_name']
    if any(not args.get(k) for k in required):
        return
    try:
        sheet = self.intern_sheet_drafter.draft(args.get('source'), args.get('name'), args.get('start_date'), args.get('end_date'), args.get('plan_name'))
    except Exception:
        return
    main = sheet.get('main_project') or {}
    scenario = sheet.get('scenario') or {}
    weeks = sheet.get('weeks') or []
    args['main_title'] = args.get('main_title') or main.get('title', '')
    args['objective'] = args.get('objective') or main.get('objective', '')
    args['tech_stack'] = args.get('tech_stack') or main.get('tech_stack', '')
    args['final_project'] = args.get('final_project') or args.get('main_title', '')
    args['scenario'] = args.get('scenario') or scenario.get('scenario', '')
    args['skills'] = args.get('skills') or scenario.get('skills', '')
    args['deliverable'] = args.get('deliverable') or scenario.get('deliverable', '')
    if weeks:
        args['schedule_preview'] = weeks

ChatService._enrich_add_intern_with_plan = _v38_enrich_add_intern_with_plan
'''

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Ensure PlanService approved Add Intern can consume schedule_preview.
# -----------------------------------------------------------------------------
s = plan_service.read_text(encoding='utf-8')
if 'def _build_schedule_from_preview' not in s:
    insert = r'''
    def _build_schedule_from_preview(self, preview: list, start: datetime, end: datetime):
        tasks = []
        week_dates = {}
        current = start
        workday_count = 0
        preview_map = {}
        for idx, item in enumerate(preview or [], start=1):
            if not isinstance(item, dict):
                continue
            week = int(item.get('week') or idx)
            preview_map[week] = {
                'theme': str(item.get('theme') or 'Learning Plan'),
                'task': str(item.get('daily_task') or item.get('task') or 'Task to be assigned'),
                'project': str(item.get('weekly_project') or f'Week {week}: Weekly Project'),
                'notes': str(item.get('notes') or ''),
            }
        while current.date() <= end.date():
            if current.weekday() < 5:
                workday_count += 1
                week = ((workday_count - 1) // 5) + 1
                item = preview_map.get(week, {'theme': 'Learning Plan', 'task': 'Task to be assigned', 'project': f'Week {week}: Weekly Project', 'notes': ''})
                week_dates.setdefault(week, []).append(current)
                tasks.append([current, week, item['theme'], item['task'], 'Pending', item.get('notes', '')])
            current += timedelta(days=1)
        weekly_reports = []
        projects = []
        for week, dates in sorted(week_dates.items()):
            item = preview_map.get(week, {'theme': 'Learning Plan', 'project': f'Week {week}: Weekly Project', 'notes': ''})
            weekly_reports.append([week, item['theme'], '', '', '', '', 'No', 'No'])
            projects.append([week, item['project'], item.get('notes') or 'To be assigned', dates[0], dates[-1], 'Pending'])
        return tasks, weekly_reports, projects

'''
    marker = '    def _build_schedule_from_plan'
    if marker not in s:
        raise SystemExit('Could not find _build_schedule_from_plan in plan_service.py')
    s = s.replace(marker, insert + marker)

old_sig = "def add_intern_with_plan(self, source_path: str, name: str, start_date: str, end_date: str, plan_name: str, output_path: str | None = None, manager: str = '', skip_manager: str = '', final_project: str = '', main_title: str = '', objective: str = '', tech_stack: str = '', scenario: str = '', skills: str = '', deliverable: str = '') -> CommandResult:"
new_sig = "def add_intern_with_plan(self, source_path: str, name: str, start_date: str, end_date: str, plan_name: str, output_path: str | None = None, manager: str = '', skip_manager: str = '', final_project: str = '', main_title: str = '', objective: str = '', tech_stack: str = '', scenario: str = '', skills: str = '', deliverable: str = '', schedule_preview: list | None = None) -> CommandResult:"
if old_sig in s:
    s = s.replace(old_sig, new_sig)

old_sched = "tasks, weekly_reports, projects = self._build_schedule_from_plan(plan, start, end)"
new_sched = "tasks, weekly_reports, projects = self._build_schedule_from_preview(schedule_preview, start, end) if schedule_preview else self._build_schedule_from_plan(plan, start, end)"
if old_sched in s:
    s = s.replace(old_sched, new_sched, 1)

plan_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 4) Ensure executor passes schedule_preview.
# -----------------------------------------------------------------------------
s = executor.read_text(encoding='utf-8')
old = "return self.plan_service.add_intern_with_plan(args[\"source\"], args[\"name\"], args[\"start_date\"], args[\"end_date\"], args[\"plan_name\"], args.get(\"output\"), args.get(\"manager\", \"\"), args.get(\"skip_manager\", \"\"), args.get(\"final_project\", \"\"), args.get(\"main_title\", \"\"), args.get(\"objective\", \"\"), args.get(\"tech_stack\", \"\"), args.get(\"scenario\", \"\"), args.get(\"skills\", \"\"), args.get(\"deliverable\", \"\"))"
new = "return self.plan_service.add_intern_with_plan(args[\"source\"], args[\"name\"], args[\"start_date\"], args[\"end_date\"], args[\"plan_name\"], args.get(\"output\"), args.get(\"manager\", \"\"), args.get(\"skip_manager\", \"\"), args.get(\"final_project\", \"\"), args.get(\"main_title\", \"\"), args.get(\"objective\", \"\"), args.get(\"tech_stack\", \"\"), args.get(\"scenario\", \"\"), args.get(\"skills\", \"\"), args.get(\"deliverable\", \"\"), args.get(\"schedule_preview\"))"
if old in s:
    s = s.replace(old, new)
executor.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 5) Chat UI: make sure schedule_preview is visible and editable before approval.
# -----------------------------------------------------------------------------
h = chat_html.read_text(encoding='utf-8')

if 'Schedule preview:' not in h:
    marker = "  if(args.scenario) html += `<p><b>Scenario:</b> ${escapeHtml(args.scenario)}</p>`;"
    addition = marker + """
  if(args.schedule_preview && Array.isArray(args.schedule_preview)){
    html += `<b>Schedule preview:</b><ul>`;
    args.schedule_preview.forEach(w=>{ html += `<li>Week ${escapeHtml(w.week)} (${escapeHtml(w.date_range || '')}): ${escapeHtml(w.theme)}<br><span class=\"hint\">Daily task: ${escapeHtml(w.daily_task || '')}<br>Weekly project: ${escapeHtml(w.weekly_project || '')}</span></li>`; });
    html += `</ul>`;
  }
"""
    if marker in h:
        h = h.replace(marker, addition)

if 'edit_schedule_box' not in h:
    old = """    html += `<label>Deliverable<textarea id="edit_deliverable">${escapeHtml(args.deliverable || '')}</textarea></label>`;\n  } else {\n"""
    new = """    html += `<label>Deliverable<textarea id="edit_deliverable">${escapeHtml(args.deliverable || '')}</textarea></label>`;\n    if(args.schedule_preview && Array.isArray(args.schedule_preview)){\n      html += '<h3>Editable Schedule Preview</h3><p class=\"hint\">Edit weekly theme, daily task, weekly project, and notes before approval. These values will be used in the intern sheet.</p>';\n      args.schedule_preview.forEach((w,i)=>{\n        html += `<div class=\"week-edit edit_schedule_box\" data-week-index=\"${i}\"><h4>Week ${escapeHtml(w.week)} (${escapeHtml(w.date_range || '')})</h4>`;\n        html += `<label>Theme<input class=\"edit_schedule_theme\" value=\"${escapeHtml(w.theme || '')}\" /></label>`;\n        html += `<label>Daily task<textarea class=\"edit_schedule_task\">${escapeHtml(w.daily_task || '')}</textarea></label>`;\n        html += `<label>Weekly project<textarea class=\"edit_schedule_project\">${escapeHtml(w.weekly_project || '')}</textarea></label>`;\n        html += `<label>Notes<textarea class=\"edit_schedule_notes\">${escapeHtml(w.notes || '')}</textarea></label>`;\n        html += `</div>`;\n      });\n    }\n  } else {\n"""
    if old in h:
        h = h.replace(old, new)

# Save edited schedule_preview when Add Intern With Plan draft is edited.
if 'edit_schedule_box' in h and 'args.schedule_preview = Array.from(sched)' not in h:
    old = """  } else if(cmd === 'add_intern_with_plan'){\n    ['name','plan_name','start_date','end_date','manager','skip_manager','main_title','objective','tech_stack','scenario','skills','deliverable'].forEach(k=>{\n      const el = document.getElementById('edit_' + k);\n      if(el) args[k] = el.value;\n    });\n  } else {\n"""
    new = """  } else if(cmd === 'add_intern_with_plan'){\n    ['name','plan_name','start_date','end_date','manager','skip_manager','main_title','objective','tech_stack','scenario','skills','deliverable'].forEach(k=>{\n      const el = document.getElementById('edit_' + k);\n      if(el) args[k] = el.value;\n    });\n    const sched = document.querySelectorAll('.edit_schedule_box');\n    if(sched.length){\n      args.schedule_preview = Array.from(sched).map((box, i)=>({\n        week: i + 1,\n        date_range: (activeProposal.args.schedule_preview && activeProposal.args.schedule_preview[i] ? activeProposal.args.schedule_preview[i].date_range : ''),\n        theme: box.querySelector('.edit_schedule_theme')?.value || '',\n        daily_task: box.querySelector('.edit_schedule_task')?.value || '',\n        weekly_project: box.querySelector('.edit_schedule_project')?.value || '',\n        notes: box.querySelector('.edit_schedule_notes')?.value || ''\n      }));\n    }\n  } else {\n"""
    if old in h:
        h = h.replace(old, new)

chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.38 Add Intern uses plan as context to draft full intern sheet

- Add Intern With Plan now asks the LLM to generate a complete intern-sheet draft using the selected plan as context.
- If the selected plan is weak/generic, the intern draft is improved instead of copying weak plan rows literally.
- The proposal preview includes main project, scenario, and week-level schedule preview.
- The Edit button can edit weekly theme, daily task, weekly project, and notes before approval.
- Approval creates the workbook from the edited draft using `schedule_preview`.
- The fallback is topic-aware for DevOps and InfoSec/SecOps and no longer exposes debug text in the workbook.
''', encoding='utf-8')

print('v0.38 intern-sheet LLM draft from plan context patch applied successfully.')
