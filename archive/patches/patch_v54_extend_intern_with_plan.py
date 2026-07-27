from pathlib import Path

root = Path(__file__).resolve().parent
plan_service = root / 'tracker_services' / 'plan_service.py'
executor = root / 'tracker_commands' / 'executor.py'
chat_service = root / 'tracker_chat' / 'chat_service.py'
readme = root / 'README.md'

for p in [plan_service, executor, chat_service]:
    if not p.exists():
        raise SystemExit(f'{p} not found. Run this patch inside intern_tracker_system_v0.')

# -----------------------------------------------------------------------------
# 1) PlanService: add extend_intern_with_plan as a safe monkey-patched method.
# -----------------------------------------------------------------------------
s = plan_service.read_text(encoding='utf-8')
if 'v0.54 extend_intern_with_plan method' not in s:
    s += r'''

# v0.54 extend_intern_with_plan method
# Adds plan-aware extension without removing the old simple Extend Intern command.
def _v54_extend_intern_with_plan(self, source_path: str, intern_name: str, new_end: str, plan_name: str, output_path: str | None = None, update_main_project: bool = True):
    from datetime import datetime, timedelta
    from tracker_commands.results import CommandResult
    from tracker_excel.renderer.parser import parse_workbook
    from tracker_excel.renderer.render_service import RenderService
    from tracker_services.version_service import VersionService
    from tracker_chat.intern_sheet_drafter import InternSheetDrafter

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

    # Draft only the extension period. The drafter uses the selected plan as context.
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

PlanService.extend_intern_with_plan = _v54_extend_intern_with_plan
'''
plan_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Executor: intercept extend_intern_with_plan.
# -----------------------------------------------------------------------------
s = executor.read_text(encoding='utf-8')
if 'v0.54 executor override for extend_intern_with_plan' not in s:
    s += r'''

# v0.54 executor override for extend_intern_with_plan
if not hasattr(CommandExecutor, '_base_execute_v54'):
    CommandExecutor._base_execute_v54 = CommandExecutor.execute


def _v54_execute(self, payload: dict):
    command = payload.get('command')
    args = payload.get('args') or {}
    if command == 'extend_intern_with_plan':
        return self.plan_service.extend_intern_with_plan(
            args['source'],
            args['intern'],
            args['new_end'],
            args['plan_name'],
            args.get('output'),
            bool(args.get('update_main_project', True))
        )
    return CommandExecutor._base_execute_v54(self, payload)

CommandExecutor.execute = _v54_execute
'''
executor.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) ChatService: route extension-with-plan prompts and required fields.
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')
if 'v0.54 extend intern with plan chat override' not in s:
    s += r'''

# v0.54 extend intern with plan chat override
LABELS['extend_intern_with_plan'] = 'Extend Intern With Plan'
REQUIRED['extend_intern_with_plan'] = ['source', 'intern', 'new_end', 'plan_name', 'output']

if not hasattr(ChatService, '_base_message_v54'):
    ChatService._base_message_v54 = ChatService.message


def _v54_chat_output(command: str):
    return f'{command}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'


def _v54_clean(value: str) -> str:
    value = (value or '').strip().strip(' .,:;')
    return ' '.join(p[:1].upper() + p[1:] for p in value.split())


def _v54_extend_with_plan_draft(self, text: str, current_workbook: str | None):
    lower = (text or '').lower()
    if 'extend' not in lower or 'with' not in lower or 'plan' not in lower:
        return None
    date_m = re.search(r'20\d{2}-\d{2}-\d{2}', text)
    if not date_m:
        return None
    args = {}
    if current_workbook:
        args['source'] = current_workbook
    args['new_end'] = date_m.group(0)

    # Extend Habeeb to 2026-09-30 with Kubernetes Troubleshooting plan
    m = re.search(r'extend\s+(?:intern\s+)?(.+?)\s+(?:to|until)\s+20\d{2}-\d{2}-\d{2}\s+with\s+(.+?)\s+plan', text, re.I)
    if m:
        args['intern'] = _v54_clean(m.group(1))
        plan = m.group(2).strip()
        # Respect exact user wording but use Foundation if just a topic.
        if 'foundation' not in plan.lower() and 'plan' not in plan.lower():
            plan = plan[:1].upper() + plan[1:] + ' Foundation'
        args['plan_name'] = plan
    args['output'] = _v54_chat_output('extend_intern_with_plan')

    # Add a flat preview note so the generic proposal is still informative.
    if args.get('intern') and args.get('plan_name'):
        args['extension_preview'] = f"Extend {args['intern']} to {args['new_end']} using {args['plan_name']}. This will generate new extension-period daily tasks, weekly projects, and update the main project/scenario to the extension focus."
    return ChatDraft(str(uuid.uuid4()), 'extend_intern_with_plan', args)


def _v54_message(self, text: str, current_workbook: str | None = None):
    draft = _v54_extend_with_plan_draft(self, text, current_workbook)
    if draft:
        return self._response_for_draft(draft)
    return ChatService._base_message_v54(self, text, current_workbook)

ChatService.message = _v54_message
'''
chat_service.write_text(s, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.54 Extend Intern With Plan

- Added `extend_intern_with_plan` workflow.
- Example: `Extend Habeeb to 2026-09-30 with Kubernetes Troubleshooting plan`.
- The workflow uses the selected extension plan as context and generates only extension-period daily tasks, weekly updates, and weekly/small projects.
- It updates intern end date and can update main project/scenario to the extension focus.
- Old simple `Extend Intern` remains available.
''', encoding='utf-8')

print('v0.54 extend intern with plan patch applied successfully.')
