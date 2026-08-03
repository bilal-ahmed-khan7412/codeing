
from datetime import datetime, timedelta
from tracker_core.models import CommandResult
from tracker_excel.renderer.parser import parse_workbook, PlanSheetData, InternSheetData
from tracker_services.render_service import RenderService
from tracker_services.version_service import VersionService
from tracker_chat.intern_sheet_drafter import InternSheetDrafter

class PlanService:


    def add_intern_with_plan(self, source_path: str, name: str, start_date: str, end_date: str, plan_name: str, output_path: str | None = None, manager: str = '', skip_manager: str = '', final_project: str = '', main_title: str = '', objective: str = '', tech_stack: str = '', scenario: str = '', skills: str = '', deliverable: str = '', schedule_preview: list | None = None) -> CommandResult:
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

        tasks, weekly_reports, projects = self._build_schedule_from_preview(schedule_preview, start, end) if schedule_preview else self._build_schedule_from_plan(plan, start, end)
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

    def create_plan_from_draft(self, source_path: str, plan_name: str, description: str = '', weeks: list | None = None, output_path: str | None = None) -> CommandResult:
        """Create a complete plan from an LLM/user-approved draft.

        weeks should be a list of dicts:
        {"week": 1, "theme": "...", "task": "...", "weekly_project": "...", "notes": "..."}
        """
        data = parse_workbook(source_path)
        plan_name = self._unique_plan_name(data, plan_name)
        weeks = weeks or []
        headers = ['Week', 'Theme', 'Task', 'Weekly Project', 'Notes']
        rows = []
        for idx, item in enumerate(weeks, start=1):
            if not isinstance(item, dict):
                continue
            rows.append([
                int(item.get('week') or idx),
                item.get('theme', ''),
                item.get('task', ''),
                item.get('weekly_project', ''),
                self._clean_visible_text(self._clean_visible_text(item.get('notes', ''), ''), ''),
            ])
        if not rows:
            rows = [[i, '', '', '', ''] for i in range(1, 9)]
        sheet_name = self._safe_sheet_name(plan_name)
        plan = PlanSheetData(
            title=f'Plan — {plan_name}',
            subtitle=description,
            headers=headers,
            rows=rows,
            sheet_name=sheet_name,
            plan_type='weekly_custom'
        )
        data.plans.append(plan)
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f'Created draft plan {plan_name}: {out}', out)

    def create_plan(self, source_path: str, plan_name: str, plan_type: str = 'weekly', description: str = '', weeks: int = 8, output_path: str | None = None) -> CommandResult:
        data = parse_workbook(source_path)
        if self._find_plan(data, plan_name):
            return CommandResult(False, f'Plan already exists: {plan_name}')
        headers = ['Week', 'Theme', 'Task', 'Weekly Project', 'Notes']
        rows = [[i, '', '', '', ''] for i in range(1, int(weeks) + 1)]
        sheet_name = self._safe_sheet_name(plan_name)
        plan = PlanSheetData(
            title=f'Plan — {plan_name}',
            subtitle=description,
            headers=headers,
            rows=rows,
            sheet_name=sheet_name,
            plan_type='weekly_custom'
        )
        data.plans.append(plan)
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f'Created plan {plan_name}: {out}', out)

    def edit_plan(self, source_path: str, plan_name: str, new_name: str | None = None, description: str | None = None, output_path: str | None = None) -> CommandResult:
        data = parse_workbook(source_path)
        plan = self._find_plan(data, plan_name)
        if not plan:
            return CommandResult(False, f'Plan not found: {plan_name}')
        if new_name:
            plan.title = f'Plan — {new_name}'
            plan.sheet_name = self._safe_sheet_name(new_name)
        if description is not None:
            plan.subtitle = description
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f'Edited plan {plan_name}: {out}', out)

    def edit_plan_week(self, source_path: str, plan_name: str, week: int, theme: str | None = None, task: str | None = None, weekly_project: str | None = None, notes: str | None = None, output_path: str | None = None) -> CommandResult:
        data = parse_workbook(source_path)
        plan = self._find_plan(data, plan_name)
        if not plan:
            return CommandResult(False, f'Plan not found: {plan_name}')
        week = int(week)
        while len(plan.rows) < week:
            plan.rows.append([len(plan.rows)+1, '', '', '', ''])
        row = plan.rows[week-1]
        while len(row) < 5:
            row.append('')
        row[0] = week
        if theme is not None: row[1] = theme
        if task is not None: row[2] = task
        if weekly_project is not None: row[3] = weekly_project
        if notes is not None: row[4] = notes
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f'Edited week {week} for plan {plan_name}: {out}', out)

    def apply_plan_to_intern(self, source_path: str, intern_name: str, plan_name: str, output_path: str | None = None) -> CommandResult:
        intern_name = (intern_name or '').strip()
        plan_name = (plan_name or '').strip()
        data = parse_workbook(source_path)
        plan = self._find_plan(data, plan_name)
        if not plan:
            return CommandResult(False, f'Plan not found: {plan_name}')
        intern = None
        for item in data.interns:
            if item.name.strip().lower() == intern_name.lower():
                intern = item
                break
        if not intern:
            return CommandResult(False, f'Intern not found: {intern_name}')
        start = intern.main_row[3] if len(intern.main_row) > 3 else None
        end = intern.main_row[4] if len(intern.main_row) > 4 else None
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            return CommandResult(False, 'Intern start/end dates are missing or invalid')
        tasks, weekly_reports, projects = self._build_schedule_from_plan(plan, start, end)
        intern.tasks = tasks
        intern.weekly_reports = weekly_reports
        intern.projects = projects
        intern.title = f'{intern.title.split("(")[0].rstrip()}    ({plan.title.replace("Plan — ", "")})'
        self._apply_project_and_scenario_defaults(intern, plan_name, start, end)
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f'Applied plan {plan_name} to {intern_name} and updated related project/scenario defaults: {out}', out)


    def _apply_project_and_scenario_defaults(self, intern, plan_name: str, start: datetime, end: datetime):
        """Set main project and real-world scenario defaults based on plan topic.

        Safety rule: overwrite only when the existing value is blank or clearly generic.
        This prevents accidental overwrite of a manager-authored capstone/scenario.
        """
        defaults = self._topic_defaults(plan_name)
        while len(intern.main_row) < 6:
            intern.main_row.append('')
        while len(intern.scenario_row) < 6:
            intern.scenario_row.append('')

        generic_project_values = {'', 'aiops', 'custom plan', 'project to be assigned', 'task to be assigned', None}
        current_title = str(intern.main_row[0]).strip().lower() if intern.main_row[0] is not None else ''
        current_objective = str(intern.main_row[1]).strip().lower() if intern.main_row[1] is not None else ''
        current_stack = str(intern.main_row[2]).strip().lower() if intern.main_row[2] is not None else ''

        if current_title in generic_project_values:
            intern.main_row[0] = defaults['project_title']
        if current_objective in generic_project_values:
            intern.main_row[1] = defaults['objective']
        if current_stack in generic_project_values:
            intern.main_row[2] = defaults['tech_stack']
        if not intern.main_row[3]:
            intern.main_row[3] = start
        intern.main_row[4] = end
        if not intern.main_row[5]:
            intern.main_row[5] = 'Pending'

        generic_scenario_values = {'', 'scenario to be assigned', 'task to be assigned', None}
        current_scenario = str(intern.scenario_row[0]).strip().lower() if intern.scenario_row[0] is not None else ''
        current_skills = str(intern.scenario_row[1]).strip().lower() if intern.scenario_row[1] is not None else ''
        current_deliverable = str(intern.scenario_row[2]).strip().lower() if intern.scenario_row[2] is not None else ''

        if current_scenario in generic_scenario_values:
            intern.scenario_row[0] = defaults['scenario']
        if current_skills in generic_scenario_values:
            intern.scenario_row[1] = defaults['skills']
        if current_deliverable in generic_scenario_values:
            intern.scenario_row[2] = defaults['deliverable']
        if not intern.scenario_row[3]:
            intern.scenario_row[3] = max(1, min(6, len(intern.weekly_reports) or 1))
        if not intern.scenario_row[4]:
            intern.scenario_row[4] = end
        if not intern.scenario_row[5]:
            intern.scenario_row[5] = 'Pending'

    def _topic_defaults(self, plan_name: str) -> dict:
        p = (plan_name or '').lower()
        if 'openshift' in p:
            return {
                'project_title': 'OpenShift Deployment and Troubleshooting Demo',
                'objective': 'Deploy, configure, monitor, and troubleshoot a sample application on OpenShift, then document the solution in a short runbook.',
                'tech_stack': 'Linux, Kubernetes, OpenShift, YAML, oc CLI, container images',
                'scenario': 'A sample application is deployed on OpenShift but has route, pod, configuration, and storage issues. The intern must investigate the failure, apply fixes, validate the deployment, and document the troubleshooting process.',
                'skills': 'OpenShift, Kubernetes, Linux, container troubleshooting, YAML, logs, routes, pods, configuration',
                'deliverable': 'Working OpenShift deployment, troubleshooting notes, validation screenshots or outputs, and a short runbook.'
            }
        if 'security' in p or 'infosec' in p or 'cyber' in p or 'soc' in p:
            return {
                'project_title': 'Information Security Assessment and Incident Triage Demo',
                'objective': 'Review security controls, investigate sample alerts, triage vulnerabilities, and produce a concise security assessment with remediation recommendations.',
                'tech_stack': 'Linux logs, SIEM concepts, IAM, vulnerability management, incident response, security checklists',
                'scenario': 'A sample environment has suspicious authentication activity, vulnerable services, and incomplete access controls. The intern must review logs, triage findings, prioritize risk, and recommend remediation steps.',
                'skills': 'Information security, log analysis, vulnerability triage, IAM review, incident response, risk assessment, reporting',
                'deliverable': 'Security assessment report, incident triage notes, prioritized remediation list, and final presentation.'
            }
        if 'kubernetes' in p or 'k8s' in p:
            return {
                'project_title': 'Kubernetes Application Deployment and Troubleshooting Demo',
                'objective': 'Deploy, expose, observe, and troubleshoot a containerized application on Kubernetes.',
                'tech_stack': 'Linux, Docker/containers, Kubernetes, kubectl, YAML, Helm basics',
                'scenario': 'A containerized application has deployment, service, configuration, and health-check issues in Kubernetes. The intern must diagnose and fix the workload.',
                'skills': 'Kubernetes, kubectl, YAML, pods, deployments, services, logs, probes, troubleshooting',
                'deliverable': 'Working Kubernetes deployment, troubleshooting report, and short demo.'
            }
        return {
            'project_title': f'{plan_name} Final Practical Demo',
            'objective': f'Complete a practical project aligned with the {plan_name} plan and document the final outcome.',
            'tech_stack': plan_name,
            'scenario': f'A realistic work scenario aligned with the {plan_name} plan requires the intern to investigate, implement, validate, and document a solution.',
            'skills': plan_name,
            'deliverable': 'Working demo, notes, and final summary report.'
        }


    def _is_debug_fallback_text(self, value) -> bool:
        text = str(value or '').strip().lower()
        debug_phrases = [
            'llm returned no detailed weeks',
            'generated safe draft',
            'adjusted to',
            'fallback',
        ]
        return any(p in text for p in debug_phrases)

    def _clean_visible_text(self, value, default: str = '') -> str:
        """Remove internal/debug notes from user-facing workbook cells."""
        if value is None:
            return default
        if self._is_debug_fallback_text(value):
            return default
        return str(value)

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
            daily_tasks = item.get('daily_tasks')
            if not isinstance(daily_tasks, list) or not daily_tasks:
                one = str(item.get('daily_task') or item.get('task') or 'Task to be assigned')
                daily_tasks = [one]
            preview_map[week] = {
                'theme': str(item.get('theme') or 'Learning Plan'),
                'daily_tasks': [str(x) for x in daily_tasks if str(x).strip()],
                'task': str(item.get('daily_task') or item.get('task') or (daily_tasks[0] if daily_tasks else 'Task to be assigned')),
                'project': str(item.get('weekly_project') or f'Week {week}: Weekly Project'),
                'notes': str(item.get('notes') or ''),
            }
        week_day_index = {}
        while current.date() <= end.date():
            if current.weekday() < 5:
                workday_count += 1
                week = ((workday_count - 1) // 5) + 1
                item = preview_map.get(week, {'theme': 'Learning Plan', 'daily_tasks': ['Task to be assigned'], 'task': 'Task to be assigned', 'project': f'Week {week}: Weekly Project', 'notes': ''})
                week_dates.setdefault(week, []).append(current)
                idx = week_day_index.get(week, 0)
                daily_list = item.get('daily_tasks') or [item.get('task', 'Task to be assigned')]
                task_text = daily_list[idx] if idx < len(daily_list) else daily_list[-1]
                week_day_index[week] = idx + 1
                tasks.append([current, week, item['theme'], task_text, 'Pending', ''])
            current += timedelta(days=1)
        weekly_reports = []
        projects = []
        for week, dates in sorted(week_dates.items()):
            item = preview_map.get(week, {'theme': 'Learning Plan', 'project': f'Week {week}: Weekly Project', 'notes': ''})
            weekly_reports.append([week, item['theme'], '', '', '', '', 'No', 'No'])
            projects.append([week, item['project'], item.get('notes') or 'To be assigned', dates[0], dates[-1], 'Pending'])
        return tasks, weekly_reports, projects

    def _build_schedule_from_plan(self, plan, start, end):
        plan_map = {}
        for row in plan.rows:
            if not row:
                continue
            try:
                w = int(row[0])
            except Exception:
                continue
            theme = row[1] if len(row) > 1 and row[1] else 'Learning Plan'
            task = row[2] if len(row) > 2 and row[2] else 'Task to be assigned'
            project = row[3] if len(row) > 3 and row[3] else f'Week {w}: Weekly Project'
            notes = self._clean_visible_text(row[4] if len(row) > 4 else '', '')
            plan_map[w] = {'theme': theme, 'task': task, 'project': project, 'notes': notes}
        tasks=[]; week_dates={}; current=start; workday_count=0
        while current.date() <= end.date():
            if current.weekday() < 5:
                workday_count += 1
                week = ((workday_count - 1)//5)+1
                item = plan_map.get(week, {'theme':'Learning Plan','task':'Task to be assigned','project':f'Week {week}: Weekly Project','notes':''})
                week_dates.setdefault(week, []).append(current)
                tasks.append([current, week, item['theme'], item['task'], 'Pending', ''])
            current += timedelta(days=1)
        weekly_reports=[]; projects=[]
        for week, dates in sorted(week_dates.items()):
            item = plan_map.get(week, {'theme':'Learning Plan','project':f'Week {week}: Weekly Project'})
            weekly_reports.append([week, item['theme'], '', '', '', '', 'No', 'No'])
            projects.append([week, item['project'], item.get('notes') or 'To be assigned', dates[0], dates[-1], 'Pending'])
        return tasks, weekly_reports, projects

    def _find_plan(self, data, name):
        q = name.lower()
        for p in data.plans:
            if q in (p.title or '').lower() or q == (p.sheet_name or '').lower():
                return p
        return None


    def _unique_plan_name(self, data, plan_name: str) -> str:
        """Return a non-conflicting plan name by adding Copy suffix if needed."""
        base = (plan_name or 'Plan').strip()
        if not self._find_plan(data, base):
            return base
        i = 2
        while True:
            candidate = f'{base} Copy {i}'
            if not self._find_plan(data, candidate):
                return candidate
            i += 1

    def _safe_sheet_name(self, name):
        bad = '[]:*?/\\'
        sheet = ''.join('_' if ch in bad else ch for ch in name)[:31]
        return sheet or 'Plan'

    def extend_intern_with_plan(self, source_path: str, intern_name: str, new_end: str, plan_name: str, output_path: str | None = None, update_main_project: bool = True,
                                 schedule_preview: list | None = None, main_title: str = '', objective: str = '', tech_stack: str = '',
                                 scenario_text: str = '', skills: str = '', deliverable: str = ''):
        """Extend an intern's end date, drafting the extension period's content from a selected plan."""
        intern_name = (intern_name or '').strip()
        plan_name = (plan_name or '').strip()
        if not intern_name or not new_end or not plan_name:
            return CommandResult(False, 'intern, new_end, and plan_name are required')

        data = parse_workbook(source_path)
        intern = None
        for item in data.interns:
            if item.name.strip().lower() == intern_name.lower():
                intern = item
                break
        if not intern:
            return CommandResult(False, f'Intern not found: {intern_name}')

        current_end = intern.main_row[4] if len(intern.main_row) > 4 else None
        if not isinstance(current_end, datetime):
            return CommandResult(False, 'Intern current end date is missing or invalid')
        try:
            new_end_dt = datetime.fromisoformat(str(new_end))
        except Exception:
            return CommandResult(False, 'new_end must be a valid ISO date, e.g. 2026-09-30')
        if new_end_dt.date() <= current_end.date():
            return CommandResult(False, 'new_end must be after the intern current end date')

        extension_start = current_end + timedelta(days=1)
        while extension_start.weekday() >= 5:
            extension_start += timedelta(days=1)

        # If the caller already has a (possibly user-edited) schedule preview
        # - i.e. this is a chat/Forms approval where the preview shown to the
        # user was built once already - use it as-is instead of drafting
        # again, so an edit to the daily tasks actually takes effect. Without
        # this, extension_schedule_preview was always regenerated fresh at
        # approval time and any edit to it was silently discarded.
        if schedule_preview:
            weeks = schedule_preview
            main = {'title': main_title, 'objective': objective, 'tech_stack': tech_stack} if (main_title or objective or tech_stack) else {}
            scenario = {'scenario': scenario_text, 'skills': skills, 'deliverable': deliverable} if (scenario_text or skills or deliverable) else {}
        else:
            drafter = InternSheetDrafter()
            draft = drafter.draft(source_path, intern_name, extension_start.strftime('%Y-%m-%d'), new_end_dt.strftime('%Y-%m-%d'), plan_name)
            weeks = draft.get('weeks') or []
            main = draft.get('main_project') or {}
            scenario = draft.get('scenario') or {}

        # Existing week/project numbering continuity.
        existing_weeks = []
        for row in getattr(intern, 'tasks', []) or []:
            try:
                existing_weeks.append(int(row[1]))
            except Exception:
                pass
        week_offset = max(existing_weeks) if existing_weeks else 0
        project_offset = len(getattr(intern, 'projects', []) or [])

        # Build extension schedule from weekly preview with progressive daily tasks.
        preview_map = {}
        for idx, w in enumerate(weeks, start=1):
            if not isinstance(w, dict):
                continue
            local_week = int(w.get('week') or idx)
            daily_tasks = w.get('daily_tasks') if isinstance(w.get('daily_tasks'), list) else []
            if not daily_tasks:
                daily_tasks = [w.get('daily_task') or w.get('task') or 'Complete extension task for this week.']
            preview_map[local_week] = {
                'theme': str(w.get('theme') or f'Extension Week {local_week}'),
                'daily_tasks': [str(x) for x in daily_tasks if str(x).strip()],
                'project': str(w.get('weekly_project') or f'Extension Week {local_week} Project'),
                'notes': str(w.get('notes') or ''),
            }

        current = extension_start
        workday_count = 0
        week_dates = {}
        week_day_index = {}
        new_tasks = []
        while current.date() <= new_end_dt.date():
            if current.weekday() < 5:
                workday_count += 1
                local_week = ((workday_count - 1) // 5) + 1
                actual_week = week_offset + local_week
                item = preview_map.get(local_week, {
                    'theme': f'{plan_name} Extension Week {local_week}',
                    'daily_tasks': [f'Complete {plan_name} extension task.'],
                    'project': f'{plan_name} Extension Project {local_week}',
                    'notes': ''
                })
                week_dates.setdefault(local_week, []).append(current)
                day_idx = week_day_index.get(local_week, 0)
                daily_list = item.get('daily_tasks') or [f'Complete {plan_name} extension task.']
                task_text = daily_list[day_idx] if day_idx < len(daily_list) else daily_list[-1]
                week_day_index[local_week] = day_idx + 1
                new_tasks.append([current, actual_week, item['theme'], task_text, 'Pending', ''])
            current += timedelta(days=1)

        new_weekly = []
        new_projects = []
        for local_week, dates in sorted(week_dates.items()):
            actual_week = week_offset + local_week
            item = preview_map.get(local_week, {'theme': f'{plan_name} Extension Week {local_week}', 'project': f'{plan_name} Extension Project {local_week}', 'notes': ''})
            new_weekly.append([actual_week, item['theme'], '', '', '', '', 'No', 'No'])
            new_projects.append([project_offset + local_week, item['project'], item.get('notes') or 'Extension deliverable', dates[0], dates[-1], 'Pending'])

        intern.tasks.extend(new_tasks)
        intern.weekly_reports.extend(new_weekly)
        intern.projects.extend(new_projects)

        # Update dates and optionally refocus project/scenario to the extension plan.
        while len(intern.main_row) < 6:
            intern.main_row.append('')
        intern.main_row[4] = new_end_dt
        if update_main_project and main:
            intern.main_row[0] = main.get('title') or intern.main_row[0]
            intern.main_row[1] = main.get('objective') or intern.main_row[1]
            intern.main_row[2] = main.get('tech_stack') or intern.main_row[2]

        while len(intern.scenario_row) < 6:
            intern.scenario_row.append('')
        if scenario:
            intern.scenario_row[0] = scenario.get('scenario') or intern.scenario_row[0]
            intern.scenario_row[1] = scenario.get('skills') or intern.scenario_row[1]
            intern.scenario_row[2] = scenario.get('deliverable') or intern.scenario_row[2]
            intern.scenario_row[4] = new_end_dt

        # Update subtitle/title.
        if len(intern.main_row) > 0 and intern.main_row[0]:
            final_project = intern.main_row[0]
        else:
            final_project = f'{plan_name} Extension Project'
        intern.subtitle = f"Start: {intern.main_row[3].strftime('%a, %d %b %Y') if len(intern.main_row) > 3 and isinstance(intern.main_row[3], datetime) else ''}    |    End: {new_end_dt.strftime('%a, %d %b %Y')}    |    Final project: {final_project}"

        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f'Extended {intern_name} to {new_end_dt.strftime("%Y-%m-%d")} with {plan_name}: {out}', out)
