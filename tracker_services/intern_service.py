import json
from datetime import datetime, timedelta
from pathlib import Path
from tracker_core.models import CommandResult
from tracker_excel.renderer.parser import parse_workbook, InternSheetData
from tracker_services.render_service import RenderService
from tracker_services.version_service import VersionService

class InternService:
    def add_intern_from_json(self, source_path: str, spec_path: str, output_path: str | None = None) -> CommandResult:
        data = parse_workbook(source_path)
        spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
        intern = self._intern_from_spec(spec)
        if any(i.name.lower() == intern.name.lower() for i in data.interns):
            return CommandResult(False, f"Intern already exists: {intern.name}")
        data.interns.append(intern)
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f"Added intern {intern.name}: {out}", out)

    def extend_internship(self, source_path: str, intern_name: str, new_end_date: str, output_path: str | None = None) -> CommandResult:
        data = parse_workbook(source_path)
        found = False
        for intern in data.interns:
            if intern.name.lower() == intern_name.lower():
                found = True
                # Keep visible subtitle simple; later this will use parsed dates properly.
                intern.subtitle = self._replace_end_in_subtitle(intern.subtitle, new_end_date)
                if len(intern.main_row) >= 5:
                    intern.main_row[4] = self._parse_date(new_end_date)
                self._extend_daily_schedule(intern, new_end_date)
        if not found:
            return CommandResult(False, f"Intern not found: {intern_name}")
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f"Extended {intern_name} to {new_end_date}: {out}", out)


    def edit_task(self, source_path: str, intern_name: str, task_ref: str, output_path: str | None = None, date: str | None = None, week: int | None = None, theme: str | None = None, task: str | None = None, status: str | None = None, remarks: str | None = None) -> CommandResult:
        """Edit an existing daily task without adding/deleting rows.

        task_ref can be:
        - 1-based daily task number
        - date in YYYY-MM-DD or supported date format
        - text contained in task description
        """
        allowed = {"Pending", "In Progress", "Completed"}
        if status is not None and status not in allowed:
            return CommandResult(False, f"Invalid status: {status}. Allowed: {', '.join(sorted(allowed))}")
        data = parse_workbook(source_path)
        intern = self._find_intern(data, intern_name)
        if not intern:
            return CommandResult(False, f"Intern not found: {intern_name}")
        idx = self._find_task_index(intern, task_ref)
        if idx is None:
            return CommandResult(False, f"Task not found for reference: {task_ref}")
        while len(intern.tasks[idx]) < 6:
            intern.tasks[idx].append('')
        if date is not None:
            intern.tasks[idx][0] = self._parse_date(date)
        if week is not None:
            intern.tasks[idx][1] = week
        if theme is not None:
            intern.tasks[idx][2] = theme
        if task is not None:
            intern.tasks[idx][3] = task
        if status is not None:
            intern.tasks[idx][4] = status
        if remarks is not None:
            intern.tasks[idx][5] = remarks
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f"Edited task for {intern.name}: {task_ref}", out, {"task_index": idx + 1})

    def update_task_status(self, source_path: str, intern_name: str, task_ref: str, status: str, output_path: str | None = None) -> CommandResult:
        """Update a daily task status by row number, date, or text contains match."""
        allowed = {"Pending", "In Progress", "Completed"}
        if status not in allowed:
            return CommandResult(False, f"Invalid status: {status}. Allowed: {', '.join(sorted(allowed))}")
        data = parse_workbook(source_path)
        intern = self._find_intern(data, intern_name)
        if not intern:
            return CommandResult(False, f"Intern not found: {intern_name}")
        idx = self._find_task_index(intern, task_ref)
        if idx is None:
            return CommandResult(False, f"Task not found for reference: {task_ref}")
        intern.tasks[idx][4] = status
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f"Updated task status for {intern.name}: {task_ref} -> {status}", out, {"task_index": idx + 1})



    def add_intern_basic(self, source_path: str, output_path: str | None = None, name: str | None = None, start_date: str | None = None, end_date: str | None = None, manager: str = '', skip_manager: str = '', plan_name: str = 'Custom Plan', final_project: str = '', main_title: str = '', objective: str = '', tech_stack: str = '', scenario: str = '', skills: str = '', deliverable: str = '') -> CommandResult:
        """Add an intern from form fields using generated placeholder schedule.

        This is the button/form friendly version of add-intern. It does not require a JSON spec.
        """
        if not name or not start_date or not end_date:
            return CommandResult(False, 'name, start_date, and end_date are required')
        data = parse_workbook(source_path)
        if any(i.name.lower() == name.lower() for i in data.interns):
            return CommandResult(False, f"Intern already exists: {name}")
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            return CommandResult(False, 'start_date and end_date must be valid dates')
        if end.date() < start.date():
            return CommandResult(False, 'end_date cannot be before start_date')

        tasks = []
        weekly_reports = []
        projects = []
        current = start
        workday_count = 0
        week_dates = {}
        while current.date() <= end.date():
            if current.weekday() < 5:
                workday_count += 1
                week = ((workday_count - 1) // 5) + 1
                week_dates.setdefault(week, []).append(current)
                tasks.append([current, week, 'Onboarding / Learning Plan', 'Task to be assigned', 'Pending', ''])
            current += timedelta(days=1)
        for week in sorted(week_dates):
            weekly_reports.append([week, 'Onboarding / Learning Plan', '', '', '', '', 'No', 'No'])
            dates = week_dates[week]
            projects.append([week, f'Week {week}: Weekly Project', 'To be assigned', dates[0], dates[-1], 'Pending'])

        title = f"Intern Tracker — {name}    ({plan_name})"
        subtitle = f"Start: {start.strftime('%a, %d %b %Y')}    |    End: {end.strftime('%a, %d %b %Y')}    |    Final project: {final_project}"
        intern = InternSheetData(
            name=name,
            title=title,
            subtitle=subtitle,
            main_headers=['Project Title','Objective','Tech Stack','Start','Target End','Status'],
            main_row=[main_title or final_project, objective, tech_stack, start, end, 'Pending'],
            scenario_headers=['Scenario','Skills Applied','Deliverable','Assigned Week','Due Date','Status'],
            scenario_row=[scenario, skills, deliverable, 1 if scenario else '', end if scenario else '', 'Pending' if scenario else ''],
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
        return CommandResult(True, f"Added intern {name} from form fields: {out}", out)

    def add_holiday(self, source_path: str, name: str, date: str, scope: str = 'global', output_path: str | None = None, intern_name: str | None = None) -> CommandResult:
        """Add a holiday into affected intern schedules.

        v0.11 policy:
        - If an affected intern already has a task on the holiday date, convert that row into a holiday row.
        - If there is no row for that date, insert a holiday schedule row in date order.
        - Holiday status is blank, so dashboard task totals do not count holidays as pending work.
        """
        holiday_date = self._parse_date(date)
        if not isinstance(holiday_date, datetime):
            return CommandResult(False, 'Holiday date must be valid')
        data = parse_workbook(source_path)
        affected = []
        for intern in data.interns:
            if scope.lower() == 'global' or (intern_name and intern.name.lower() == intern_name.lower()):
                affected.append(intern)
        if not affected:
            return CommandResult(False, 'No interns matched the holiday scope')
        for intern in affected:
            self._apply_holiday_to_intern(intern, name, holiday_date)
            data.holidays.append([name, holiday_date, scope, intern.name, True])
        out = output_path or VersionService.next_version_path(source_path)
        note = f"Added holiday {name} on {date} for {len(affected)} intern(s)"
        RenderService.render_data(data, out, version_action='add_holiday', version_note=note)
        return CommandResult(True, note, out)

    def _apply_holiday_to_intern(self, intern, holiday_name: str, holiday_date: datetime):
        # Convert existing date row if present.
        for task in intern.tasks:
            if task and isinstance(task[0], datetime) and task[0].date() == holiday_date.date():
                task[2] = f'HOLIDAY — {holiday_name}'
                task[3] = holiday_name
                task[4] = ''
                task[5] = 'Holiday'
                return
        # Otherwise insert a new row keeping date order.
        weeks = [t[1] for t in intern.tasks if len(t) > 1 and isinstance(t[1], int) and isinstance(t[0], datetime) and t[0].date() < holiday_date.date()]
        week = weeks[-1] if weeks else 1
        row = [holiday_date, week, f'HOLIDAY — {holiday_name}', holiday_name, '', 'Holiday']
        idx = 0
        while idx < len(intern.tasks):
            tdate = intern.tasks[idx][0] if intern.tasks[idx] else None
            if isinstance(tdate, datetime) and tdate.date() > holiday_date.date():
                break
            idx += 1
        intern.tasks.insert(idx, row)

    def update_scenario(self, source_path: str, intern_name: str, output_path: str | None = None, scenario: str | None = None, skills: str | None = None, deliverable: str | None = None, assigned_week: int | None = None, due_date: str | None = None, status: str | None = None) -> CommandResult:
        """Update the REAL-WORLD SCENARIO section for an intern."""
        allowed = {"Pending", "In Progress", "Completed"}
        if status is not None and status not in allowed:
            return CommandResult(False, f"Invalid status: {status}. Allowed: {', '.join(sorted(allowed))}")
        data = parse_workbook(source_path)
        intern = self._find_intern(data, intern_name)
        if not intern:
            return CommandResult(False, f"Intern not found: {intern_name}")
        while len(intern.scenario_row) < 6:
            intern.scenario_row.append('')
        if scenario is not None:
            intern.scenario_row[0] = scenario
        if skills is not None:
            intern.scenario_row[1] = skills
        if deliverable is not None:
            intern.scenario_row[2] = deliverable
        if assigned_week is not None:
            intern.scenario_row[3] = assigned_week
        if due_date is not None:
            intern.scenario_row[4] = self._parse_date(due_date)
        if status is not None:
            intern.scenario_row[5] = status
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f"Updated scenario for {intern.name}", out)

    def edit_project(self, source_path: str, intern_name: str, project_number: int, output_path: str | None = None, title: str | None = None, description: str | None = None, assigned_date: str | None = None, due_date: str | None = None, status: str | None = None) -> CommandResult:
        """Edit an existing small/weekly project without adding or deleting rows."""
        allowed = {"Pending", "In Progress", "Completed"}
        if status is not None and status not in allowed:
            return CommandResult(False, f"Invalid status: {status}. Allowed: {', '.join(sorted(allowed))}")
        data = parse_workbook(source_path)
        intern = self._find_intern(data, intern_name)
        if not intern:
            return CommandResult(False, f"Intern not found: {intern_name}")
        project = None
        for p in intern.projects:
            if p and str(p[0]) == str(project_number):
                project = p
                break
        if project is None:
            return CommandResult(False, f"Project #{project_number} not found for {intern.name}")
        while len(project) < 6:
            project.append('')
        if title is not None:
            project[1] = title
        if description is not None:
            project[2] = description
        if assigned_date is not None:
            project[3] = self._parse_date(assigned_date)
        if due_date is not None:
            project[4] = self._parse_date(due_date)
        if status is not None:
            project[5] = status
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f"Edited project #{project_number} for {intern.name}", out)

    def edit_task_remarks(self, source_path: str, intern_name: str, task_ref: str, remarks: str, output_path: str | None = None) -> CommandResult:
        data = parse_workbook(source_path)
        intern = self._find_intern(data, intern_name)
        if not intern:
            return CommandResult(False, f"Intern not found: {intern_name}")
        idx = self._find_task_index(intern, task_ref)
        if idx is None:
            return CommandResult(False, f"Task not found for reference: {task_ref}")
        while len(intern.tasks[idx]) < 6:
            intern.tasks[idx].append('')
        intern.tasks[idx][5] = remarks
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f"Updated task remarks for {intern.name}: {task_ref}", out, {"task_index": idx + 1})

    def update_capstone(self, source_path: str, intern_name: str, output_path: str | None = None, title: str | None = None, objective: str | None = None, tech_stack: str | None = None, status: str | None = None, target_end: str | None = None) -> CommandResult:
        data = parse_workbook(source_path)
        intern = self._find_intern(data, intern_name)
        if not intern:
            return CommandResult(False, f"Intern not found: {intern_name}")
        if title is not None: intern.main_row[0] = title
        if objective is not None: intern.main_row[1] = objective
        if tech_stack is not None: intern.main_row[2] = tech_stack
        if target_end is not None: intern.main_row[4] = self._parse_date(target_end)
        if status is not None: intern.main_row[5] = status
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f"Updated capstone for {intern.name}", out)

    def update_project_status(self, source_path: str, intern_name: str, project_number: int, status: str, output_path: str | None = None) -> CommandResult:
        allowed = {"Pending", "In Progress", "Completed"}
        if status not in allowed:
            return CommandResult(False, f"Invalid status: {status}. Allowed: {', '.join(sorted(allowed))}")
        data = parse_workbook(source_path)
        intern = self._find_intern(data, intern_name)
        if not intern:
            return CommandResult(False, f"Intern not found: {intern_name}")
        found = False
        for project in intern.projects:
            if project and str(project[0]) == str(project_number):
                while len(project) < 6:
                    project.append('')
                project[5] = status
                found = True
                break
        if not found:
            return CommandResult(False, f"Project #{project_number} not found for {intern.name}")
        out = output_path or VersionService.next_version_path(source_path)
        RenderService.render_data(data, out)
        return CommandResult(True, f"Updated project #{project_number} for {intern.name} -> {status}", out)

    def _find_intern(self, data, intern_name: str):
        for intern in data.interns:
            if intern.name.lower() == intern_name.lower():
                return intern
        return None

    def _find_task_index(self, intern, task_ref: str):
        # 1-based row number within daily tasks
        if task_ref.isdigit():
            idx = int(task_ref) - 1
            if 0 <= idx < len(intern.tasks):
                return idx
        # date match
        parsed = self._parse_date(task_ref)
        if isinstance(parsed, datetime):
            for idx, task in enumerate(intern.tasks):
                if task and isinstance(task[0], datetime) and task[0].date() == parsed.date():
                    return idx
        # contains match against task description
        q = task_ref.lower()
        for idx, task in enumerate(intern.tasks):
            if len(task) > 3 and task[3] and q in str(task[3]).lower():
                return idx
        return None

    def _extend_daily_schedule(self, intern, new_end_date: str):
        """Append blank extension workday rows and weekly report rows up to new_end_date.

        Extension policy v0:
        - Use the last dated daily task as the current schedule end.
        - Add Monday-Friday rows only.
        - Add placeholder task text so manager/LLM can edit later.
        - Continue week numbering in 5-workday blocks after the current max week.
        """
        new_end = self._parse_date(new_end_date)
        if not isinstance(new_end, datetime):
            return
        dated_tasks = [t for t in intern.tasks if t and isinstance(t[0], datetime)]
        if not dated_tasks:
            return
        last_date = max(t[0] for t in dated_tasks)
        if new_end.date() <= last_date.date():
            return
        existing_weeks = [t[1] for t in intern.tasks if len(t) > 1 and isinstance(t[1], int)]
        base_week = max(existing_weeks) if existing_weeks else 0
        current = last_date + timedelta(days=1)
        workday_count = 0
        new_weeks = set()
        week_dates = {}
        while current.date() <= new_end.date():
            if current.weekday() < 5:
                workday_count += 1
                week = base_week + ((workday_count - 1) // 5) + 1
                new_weeks.add(week)
                week_dates.setdefault(week, []).append(current)
                intern.tasks.append([current, week, 'Extension Period', 'Task to be assigned', 'Pending', ''])
            current += timedelta(days=1)

        # Extend weekly updates for the new weeks.
        existing_report_weeks = {r[0] for r in intern.weekly_reports if r and isinstance(r[0], int)}
        for week in sorted(new_weeks):
            if week not in existing_report_weeks:
                intern.weekly_reports.append([week, 'Extension Period', '', '', '', '', 'No', 'No'])

        # Extend small projects / weekly projects for the new weeks.
        # v0.4 policy: if no project content is provided, create safe placeholders.
        existing_project_numbers = {int(p[0]) for p in intern.projects if p and str(p[0]).isdigit()}
        next_number = max(existing_project_numbers) + 1 if existing_project_numbers else 1
        for week in sorted(new_weeks):
            if week in existing_project_numbers:
                continue
            dates = week_dates.get(week, [])
            assigned_date = dates[0] if dates else None
            due_date = dates[-1] if dates else None
            intern.projects.append([
                week,
                f'Week {week}: Extension Project',
                'To be assigned',
                assigned_date,
                due_date,
                'Pending'
            ])
            existing_project_numbers.add(week)

    def _replace_end_in_subtitle(self, subtitle: str, new_end: str) -> str:
        if 'End:' in subtitle and '|' in subtitle:
            parts = subtitle.split('|')
            for idx,p in enumerate(parts):
                if 'End:' in p:
                    parts[idx] = f"    End: {new_end}    "
            return '|'.join(parts)
        return subtitle + f" | End: {new_end}"

    def _parse_date(self, value):
        if not value:
            return None
        for fmt in ['%Y-%m-%d','%d-%b-%Y','%d %b %Y','%d/%m/%Y']:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
        return value

    def _intern_from_spec(self, spec: dict) -> InternSheetData:
        name = spec['name']
        plan = spec.get('plan_name','Custom')
        title = spec.get('title') or f"Intern Tracker — {name}    ({plan})"
        subtitle = spec.get('subtitle') or f"Start: {spec.get('start_date','')}    |    End: {spec.get('end_date','')}    |    Final project: {spec.get('final_project','')}"
        main = spec.get('main_project', {})
        scenario = spec.get('scenario', {})
        tasks = spec.get('tasks', [])
        weekly_reports = spec.get('weekly_reports') or self._default_weekly_reports(tasks)
        projects = spec.get('projects', [])
        return InternSheetData(
            name=name,
            title=title,
            subtitle=subtitle,
            main_headers=['Project Title','Objective','Tech Stack','Start','Target End','Status'],
            main_row=[main.get('title',''), main.get('objective',''), main.get('tech_stack',''), self._parse_date(spec.get('start_date')), self._parse_date(spec.get('end_date')), main.get('status','Pending')],
            scenario_headers=['Scenario','Skills Applied','Deliverable','Assigned Week','Due Date','Status'],
            scenario_row=[scenario.get('scenario',''), scenario.get('skills',''), scenario.get('deliverable',''), scenario.get('assigned_week',''), self._parse_date(scenario.get('due_date')), scenario.get('status','Pending')],
            task_headers=['Date','Week','Theme','Task Description','Status (Pending/In Progress/Completed)','Remarks'],
            tasks=[[self._parse_date(t.get('date')), t.get('week'), t.get('theme',''), t.get('task',''), t.get('status','Pending'), t.get('remarks','')] for t in tasks],
            weekly_headers=['Week #','Theme','Highlights','Blockers','Tasks Completed','Manager Comments','Email Sent','Line Manager Acknowledged'],
            weekly_reports=weekly_reports,
            project_title=spec.get('project_section_title','SMALL PROJECTS / TASKS'),
            project_headers=['#','Title','Description','Assigned Date','Due Date','Status'],
            projects=[[p.get('number',''), p.get('title',''), p.get('description',''), self._parse_date(p.get('assigned_date')), self._parse_date(p.get('due_date')), p.get('status','Pending')] for p in projects]
        )

    def _default_weekly_reports(self, tasks):
        weeks = sorted({t.get('week') for t in tasks if isinstance(t.get('week'), int)})
        if not weeks: weeks = [1]
        themes = {}
        for t in tasks:
            if isinstance(t.get('week'), int) and t.get('week') not in themes:
                themes[t.get('week')] = t.get('theme','')
        return [[w, themes.get(w,''), '', '', '', '', 'No', 'No'] for w in weeks]
