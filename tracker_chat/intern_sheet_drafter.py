
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

    def _get_provider(self):
        from tracker_llm.provider_context import current_provider
        return current_provider.get() or self.provider

    def draft(self, source: str, name: str, start_date: str, end_date: str, plan_name: str) -> dict:
        source_path = resolve_workbook_path(source)
        plan_context = self._load_plan_context(source_path, plan_name)
        week_ranges = self._week_ranges(start_date, end_date)
        week_count = len(week_ranges) or 8
        if self._get_provider():
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
- Each week must include daily_tasks as a list of 5 progressive, specific, hands-on tasks relevant to {plan_name}. Each day should build on the previous day.
- Each weekly_project must be a concrete deliverable.
- The weeks as a whole must escalate across the entire internship, not just within a week: early weeks cover fundamentals and setup, middle weeks apply and integrate skills into more complex, realistic work, and the final week(s) focus specifically on completing, polishing, and presenting the main project.
- No two weeks may share a similar or repeated theme, daily_tasks, or weekly_project - every week must be clearly more advanced than every earlier week and must build on what was covered before it.
- Never use these phrases: task to be assigned, core concepts, hands-on practice, final demo, foundation and environment setup, LLM returned no detailed weeks, generated safe draft.
- If plan context is generic, improve it into a strong {plan_name} internship plan.
"""
        try:
            data = self._get_provider().complete_json(prompt)
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
        seen_themes = set()
        for w in weeks[:week_count]:
            if not isinstance(w, dict):
                return False
            daily_tasks = w.get('daily_tasks')
            if not isinstance(daily_tasks, list) or len([x for x in daily_tasks if str(x).strip()]) < 3:
                # Backward compatibility: allow one daily_task but it is weaker.
                if len(str(w.get('daily_task', '')).strip()) < 35:
                    return False
            text = ' '.join(str(w.get(k, '')) for k in ['theme', 'daily_task', 'weekly_project', 'notes']).lower()
            if isinstance(daily_tasks, list):
                text += ' ' + ' '.join(str(x) for x in daily_tasks).lower()
            if any(x in text for x in bad):
                return False
            if len(str(w.get('weekly_project', '')).strip()) < 20:
                return False
            # Reject a draft that just repeats the same week theme instead of
            # escalating across the internship - forces the fallback path
            # (which itself never literally repeats) rather than accepting
            # near-identical weeks from a lazy LLM response.
            theme_key = str(w.get('theme', '')).strip().lower()
            if theme_key and theme_key in seen_themes:
                return False
            seen_themes.add(theme_key)
        return True

    def _merge_dates(self, data: dict, week_ranges: list[dict]) -> dict:
        weeks = data.get('weeks') or []
        merged = []
        for i, wr in enumerate(week_ranges):
            w = weeks[i] if i < len(weeks) and isinstance(weeks[i], dict) else {}
            raw_daily_tasks = w.get('daily_tasks')
            distinct = {str(x).strip() for x in raw_daily_tasks if str(x).strip()} if isinstance(raw_daily_tasks, list) else set()
            if not isinstance(raw_daily_tasks, list) or not raw_daily_tasks or len(distinct) < 3:
                # _is_good_draft only checks that daily_tasks has enough
                # non-empty entries, not that they're actually different -
                # a lazy LLM response repeating the same weekly summary 5
                # times passes that check and shows up as 5 identical "Day
                # N" rows in the edit-draft UI. Re-expand into genuinely
                # distinct entries whenever what came back isn't.
                fallback_one = clean_debug_text(w.get('daily_task'), 'Complete assigned practical tasks for this week.')
                raw_daily_tasks = self._expand_to_daily_tasks(fallback_one, w.get('theme') or f"Week {wr['week']} Learning")
            merged.append({
                'week': wr['week'],
                'date_range': wr['date_range'],
                'theme': clean_debug_text(w.get('theme'), f"Week {wr['week']} Learning"),
                'daily_task': clean_debug_text(raw_daily_tasks[0] if raw_daily_tasks else w.get('daily_task'), 'Complete assigned practical tasks for this week.'),
                'daily_tasks': [clean_debug_text(x, 'Complete assigned practical task.') for x in raw_daily_tasks[:5]],
                'weekly_project': clean_debug_text(w.get('weekly_project'), f"Week {wr['week']} deliverable"),
                'notes': clean_debug_text(w.get('notes'), ''),
            })
        return {
            'main_project': data.get('main_project') or {},
            'scenario': data.get('scenario') or {},
            'weeks': merged,
        }

    def _expand_to_daily_tasks(self, weekly_task: str, theme: str) -> list[str]:
        weekly_task = clean_debug_text(weekly_task, '')
        theme = clean_debug_text(theme, 'Weekly topic')
        if not weekly_task:
            weekly_task = f'Practice and apply {theme} concepts.'
        return [
            f'Introduce {theme}: review goals, setup requirements, and complete guided practice.',
            f'Practice {theme}: complete focused hands-on exercises and record key commands or steps.',
            f'Apply {theme}: work through a realistic scenario and capture observations or issues.',
            f'Troubleshoot {theme}: identify common errors, validate fixes, and document lessons learned.',
            f'Consolidate {theme}: complete the weekly deliverable and summarize outcomes.'
        ]

    def _fallback_daily_tasks(self, theme: str, weekly_task: str, weekly_project: str) -> list[str]:
        theme = clean_debug_text(theme, 'Weekly topic')
        weekly_task = clean_debug_text(weekly_task, f'Practice {theme}.')
        weekly_project = clean_debug_text(weekly_project, 'weekly deliverable')
        return [
            f'Understand {theme}: review objectives, setup required tools, and complete guided examples.',
            f'Practice {theme}: perform hands-on exercises related to {weekly_task.lower()}',
            f'Apply {theme}: complete a small practical scenario and document commands, configuration, or observations.',
            f'Troubleshoot {theme}: inspect errors, validate fixes, and record lessons learned.',
            f'Complete the week deliverable: {weekly_project}'
        ]

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
        n = len(week_ranges)
        progressive = base[:-1]  # every theme except the final "wrap up the project" one
        for i, wr in enumerate(week_ranges):
            if n <= len(base):
                # Short enough plan - the base list already ends on the final
                # project theme, so a plain index-through covers it exactly.
                theme, daily_task, weekly_project, notes = base[i]
            elif i == n - 1:
                # Longer plan - always land the true last week on the final
                # project theme, regardless of where the cycle below is at.
                theme, daily_task, weekly_project, notes = base[-1]
            else:
                cycle = i // len(progressive)
                theme, daily_task, weekly_project, notes = progressive[i % len(progressive)]
                if cycle > 0:
                    # Repeating the 8-theme cycle for a long plan - escalate
                    # instead of silently repeating the same week verbatim.
                    theme = f"{theme} (Advanced Round {cycle + 1})"
                    daily_task = f"Deepen and extend: {daily_task} Apply this at a more advanced level than the earlier pass, with less guidance and higher expectations."
                    weekly_project = f"Advanced iteration: {weekly_project} Extend the scope and complexity beyond the earlier version of this deliverable."
            weeks.append({'week': wr['week'], 'date_range': wr['date_range'], 'theme': theme, 'daily_task': daily_task, 'daily_tasks': self._fallback_daily_tasks(theme, daily_task, weekly_project), 'weekly_project': weekly_project, 'notes': notes})
        return {'main_project': main, 'scenario': scenario, 'weeks': weeks}
