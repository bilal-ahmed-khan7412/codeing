from pathlib import Path

root = Path(__file__).resolve().parent
intern_drafter = root / 'tracker_chat' / 'intern_sheet_drafter.py'
plan_service = root / 'tracker_services' / 'plan_service.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

for p in [intern_drafter, plan_service, chat_html]:
    if not p.exists():
        raise SystemExit(f'{p} not found. Apply v0.38 first, then run this patch inside intern_tracker_system_v0.')

# -----------------------------------------------------------------------------
# 1) InternSheetDrafter: ask/produce progressive daily task lists.
# -----------------------------------------------------------------------------
s = intern_drafter.read_text(encoding='utf-8')

# Update LLM prompt JSON shape and quality rules.
s = s.replace(
'''    {
      "week": 1,
      "theme": "specific week theme",
      "daily_task": "specific daily task focus for that week, detailed and actionable",
      "weekly_project": "specific weekly project/deliverable",
      "notes": "short outcome or validation criteria"
    }''',
'''    {
      "week": 1,
      "theme": "specific week theme",
      "daily_tasks": [
        "Day 1 specific task",
        "Day 2 specific task",
        "Day 3 specific task",
        "Day 4 specific task",
        "Day 5 specific task"
      ],
      "weekly_project": "specific weekly project/deliverable",
      "notes": "short outcome or validation criteria"
    }'''
)
s = s.replace(
'- Each daily_task must be specific, hands-on, and relevant to {plan_name}.',
'- Each week must include daily_tasks as a list of 5 progressive, specific, hands-on tasks relevant to {plan_name}. Each day should build on the previous day.'
)
s = s.replace(
"- Never use these phrases: task to be assigned, core concepts, hands-on practice, final demo, foundation and environment setup, LLM returned no detailed weeks, generated safe draft.",
"- Never use these phrases: task to be assigned, core concepts, hands-on practice, final demo, foundation and environment setup, LLM returned no detailed weeks, generated safe draft."
)

# Replace _is_good_draft to validate daily_tasks when present.
start = s.find('    def _is_good_draft(self, data, week_count: int) -> bool:')
end = s.find('\n    def _merge_dates', start)
if start == -1 or end == -1:
    raise SystemExit('Could not find _is_good_draft block in intern_sheet_drafter.py')
new_good = r'''    def _is_good_draft(self, data, week_count: int) -> bool:
        if not isinstance(data, dict):
            return False
        weeks = data.get('weeks')
        if not isinstance(weeks, list) or len(weeks) < week_count:
            return False
        bad = ['task to be assigned', 'core concepts', 'hands-on practice', 'final demo', 'foundation and environment setup', 'llm returned no detailed weeks', 'generated safe draft']
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
        return True
'''
s = s[:start] + new_good + s[end:]

# Replace _merge_dates to emit daily_tasks.
start = s.find('    def _merge_dates(self, data: dict, week_ranges: list[dict]) -> dict:')
end = s.find('\n    def _fallback_draft', start)
if start == -1 or end == -1:
    raise SystemExit('Could not find _merge_dates block in intern_sheet_drafter.py')
new_merge = r'''    def _merge_dates(self, data: dict, week_ranges: list[dict]) -> dict:
        weeks = data.get('weeks') or []
        merged = []
        for i, wr in enumerate(week_ranges):
            w = weeks[i] if i < len(weeks) and isinstance(weeks[i], dict) else {}
            raw_daily_tasks = w.get('daily_tasks')
            if not isinstance(raw_daily_tasks, list) or not raw_daily_tasks:
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
'''
s = s[:start] + new_merge + s[end:]

# Replace fallback weeks creation to include 5 progressive daily_tasks from each weekly daily_task.
old = "weeks.append({'week': wr['week'], 'date_range': wr['date_range'], 'theme': b[0], 'daily_task': b[1], 'weekly_project': b[2], 'notes': b[3]})"
new = "weeks.append({'week': wr['week'], 'date_range': wr['date_range'], 'theme': b[0], 'daily_task': b[1], 'daily_tasks': self._fallback_daily_tasks(b[0], b[1], b[2]), 'weekly_project': b[2], 'notes': b[3]})"
if old in s:
    s = s.replace(old, new)
else:
    print('Warning: fallback weeks append not found; daily_tasks may not be added to fallback.')

# Add fallback_daily_tasks helper before _fallback_draft if missing.
if 'def _fallback_daily_tasks' not in s:
    insert_at = s.find('    def _fallback_draft')
    helper = r'''    def _fallback_daily_tasks(self, theme: str, weekly_task: str, weekly_project: str) -> list[str]:
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

'''
    if insert_at == -1:
        raise SystemExit('Could not find _fallback_draft insertion point.')
    s = s[:insert_at] + helper + s[insert_at:]

intern_drafter.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) PlanService: create daily rows from weekly daily_tasks list.
# -----------------------------------------------------------------------------
s = plan_service.read_text(encoding='utf-8')

# Replace _build_schedule_from_preview if present.
start = s.find('    def _build_schedule_from_preview(self, preview: list, start: datetime, end: datetime):')
if start == -1:
    raise SystemExit('Could not find _build_schedule_from_preview in plan_service.py. Apply v0.38 first.')
end = s.find('\n    def _build_schedule_from_plan', start)
if end == -1:
    raise SystemExit('Could not locate end of _build_schedule_from_preview.')
new_func = r'''    def _build_schedule_from_preview(self, preview: list, start: datetime, end: datetime):
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
'''
s = s[:start] + new_func + s[end:]

plan_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Chat UI: show and edit per-day tasks.
# -----------------------------------------------------------------------------
h = chat_html.read_text(encoding='utf-8')

# Display daily_tasks list in proposal if available.
old = "Daily task: ${escapeHtml(w.daily_task || '')}<br>Weekly project: ${escapeHtml(w.weekly_project || '')}"
new = "Daily tasks: ${escapeHtml((w.daily_tasks && Array.isArray(w.daily_tasks)) ? w.daily_tasks.join(' | ') : (w.daily_task || ''))}<br>Weekly project: ${escapeHtml(w.weekly_project || '')}"
h = h.replace(old, new)

# In Edit form, add daily task fields instead of one daily task textarea.
old_block = """        html += `<label>Daily task<textarea class=\"edit_schedule_task\">${escapeHtml(w.daily_task || '')}</textarea></label>`;\n        html += `<label>Weekly project<textarea class=\"edit_schedule_project\">${escapeHtml(w.weekly_project || '')}</textarea></label>`;"""
new_block = """        const dayTasks = (w.daily_tasks && Array.isArray(w.daily_tasks) && w.daily_tasks.length) ? w.daily_tasks : [w.daily_task || ''];\n        html += '<label>Daily tasks</label>';\n        for(let d=0; d<5; d++){ html += `<label>Day ${d+1}<textarea class=\"edit_schedule_day_task\" data-day-index=\"${d}\">${escapeHtml(dayTasks[d] || dayTasks[dayTasks.length-1] || '')}</textarea></label>`; }\n        html += `<label>Weekly project<textarea class=\"edit_schedule_project\">${escapeHtml(w.weekly_project || '')}</textarea></label>`;"""
if old_block in h:
    h = h.replace(old_block, new_block)
else:
    print('Warning: edit daily task block not found in chat.html.')

# Save daily_tasks array.
old_save = """        daily_task: box.querySelector('.edit_schedule_task')?.value || '',\n        weekly_project: box.querySelector('.edit_schedule_project')?.value || '',"""
new_save = """        daily_task: (Array.from(box.querySelectorAll('.edit_schedule_day_task')).map(x=>x.value).filter(Boolean)[0] || ''),\n        daily_tasks: Array.from(box.querySelectorAll('.edit_schedule_day_task')).map(x=>x.value).filter(Boolean),\n        weekly_project: box.querySelector('.edit_schedule_project')?.value || '',"""
if old_save in h:
    h = h.replace(old_save, new_save)
else:
    print('Warning: save daily task block not found in chat.html.')

chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.40 Progressive daily tasks inside each weekly theme

- Add Intern With Plan now creates progressive daily tasks within each week instead of repeating the same task every day.
- Schedule preview supports `daily_tasks` per week.
- Intern sheet daily rows use Day 1, Day 2, Day 3, etc. tasks while keeping the same weekly theme.
- Edit proposal now allows editing Day 1 to Day 5 tasks for each week.
''', encoding='utf-8')

print('v0.40 progressive daily tasks patch applied successfully.')
