from pathlib import Path

root = Path(__file__).resolve().parent
plan_service = root / 'tracker_services' / 'plan_service.py'
executor = root / 'tracker_commands' / 'executor.py'
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

for p in [plan_service, executor, chat_service, chat_html]:
    if not p.exists():
        raise SystemExit(f'{p} not found. Run this patch inside intern_tracker_system_v0 after the chat/workflow patches.')

# -----------------------------------------------------------------------------
# 1) PlanService: hide debug fallback notes from Excel and support edited schedule previews.
# -----------------------------------------------------------------------------
s = plan_service.read_text(encoding='utf-8')

# Add helper methods before _build_schedule_from_plan.
if 'def _clean_visible_text' not in s:
    helper = r'''
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
        """Build intern schedule from an approved/edited chat preview.

        Preview items should be dicts with week, theme, daily_task, weekly_project, notes.
        This lets users edit the generated schedule before workbook creation.
        """
        preview_map = {}
        for idx, item in enumerate(preview or [], start=1):
            if not isinstance(item, dict):
                continue
            try:
                week = int(item.get('week') or idx)
            except Exception:
                week = idx
            preview_map[week] = {
                'theme': self._clean_visible_text(item.get('theme'), 'Learning Plan'),
                'task': self._clean_visible_text(item.get('daily_task') or item.get('task'), 'Task to be assigned'),
                'project': self._clean_visible_text(item.get('weekly_project'), f'Week {week}: Weekly Project'),
                'notes': self._clean_visible_text(item.get('notes'), ''),
            }
        tasks = []
        week_dates = {}
        current = start
        workday_count = 0
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
    s = s.replace(marker, helper + marker)

# Sanitize notes in create_plan_from_draft row creation.
s = s.replace("item.get('notes', ''),", "self._clean_visible_text(item.get('notes', ''), ''),")

# Sanitize notes in _build_schedule_from_plan.
s = s.replace("notes = row[4] if len(row) > 4 else ''", "notes = self._clean_visible_text(row[4] if len(row) > 4 else '', '')")
s = s.replace("projects.append([week, item['project'], item.get('notes','To be assigned'), dates[0], dates[-1], 'Pending'])", "projects.append([week, item['project'], item.get('notes') or 'To be assigned', dates[0], dates[-1], 'Pending'])")

# Add schedule_preview parameter to add_intern_with_plan signature and use it.
old_sig = "def add_intern_with_plan(self, source_path: str, name: str, start_date: str, end_date: str, plan_name: str, output_path: str | None = None, manager: str = '', skip_manager: str = '', final_project: str = '', main_title: str = '', objective: str = '', tech_stack: str = '', scenario: str = '', skills: str = '', deliverable: str = '') -> CommandResult:"
new_sig = "def add_intern_with_plan(self, source_path: str, name: str, start_date: str, end_date: str, plan_name: str, output_path: str | None = None, manager: str = '', skip_manager: str = '', final_project: str = '', main_title: str = '', objective: str = '', tech_stack: str = '', scenario: str = '', skills: str = '', deliverable: str = '', schedule_preview: list | None = None) -> CommandResult:"
if old_sig in s:
    s = s.replace(old_sig, new_sig)

old_sched = "tasks, weekly_reports, projects = self._build_schedule_from_plan(plan, start, end)"
new_sched = "tasks, weekly_reports, projects = self._build_schedule_from_preview(schedule_preview, start, end) if schedule_preview else self._build_schedule_from_plan(plan, start, end)"
# Replace only in add_intern_with_plan occurrence, but safe if global okay.
if old_sched in s:
    s = s.replace(old_sched, new_sched, 1)

plan_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Executor: pass edited schedule_preview into add_intern_with_plan.
# -----------------------------------------------------------------------------
s = executor.read_text(encoding='utf-8')
old = "return self.plan_service.add_intern_with_plan(args[\"source\"], args[\"name\"], args[\"start_date\"], args[\"end_date\"], args[\"plan_name\"], args.get(\"output\"), args.get(\"manager\", \"\"), args.get(\"skip_manager\", \"\"), args.get(\"final_project\", \"\"), args.get(\"main_title\", \"\"), args.get(\"objective\", \"\"), args.get(\"tech_stack\", \"\"), args.get(\"scenario\", \"\"), args.get(\"skills\", \"\"), args.get(\"deliverable\", \"\"))"
new = "return self.plan_service.add_intern_with_plan(args[\"source\"], args[\"name\"], args[\"start_date\"], args[\"end_date\"], args[\"plan_name\"], args.get(\"output\"), args.get(\"manager\", \"\"), args.get(\"skip_manager\", \"\"), args.get(\"final_project\", \"\"), args.get(\"main_title\", \"\"), args.get(\"objective\", \"\"), args.get(\"tech_stack\", \"\"), args.get(\"scenario\", \"\"), args.get(\"skills\", \"\"), args.get(\"deliverable\", \"\"), args.get(\"schedule_preview\"))"
if old in s:
    s = s.replace(old, new)
executor.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) ChatService: warn on weak plan quality and keep schedule_preview at approval.
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

if 'def _plan_quality_warnings' not in s:
    helper = r'''
    def _plan_quality_warnings(self, weeks: list, plan_name: str = '') -> list[str]:
        warnings = []
        if not isinstance(weeks, list) or not weeks:
            return ['No detailed weekly plan content was generated.']
        generic_phrases = ['task to be assigned', 'foundation and environment setup', 'core concepts', 'hands-on practice', 'final demo', 'llm returned no detailed weeks', 'generated safe draft']
        generic_count = 0
        short_count = 0
        for w in weeks:
            text = ' '.join(str(w.get(k, '')) for k in ['theme', 'task', 'weekly_project', 'notes'] if isinstance(w, dict)).lower()
            if any(p in text for p in generic_phrases):
                generic_count += 1
            if isinstance(w, dict) and (len(str(w.get('task', '')).strip()) < 25 or len(str(w.get('weekly_project', '')).strip()) < 15):
                short_count += 1
        if generic_count:
            warnings.append(f'{generic_count} week(s) look generic or fallback-based.')
        if short_count:
            warnings.append(f'{short_count} week(s) have very short task/project details.')
        return warnings

'''
    marker = '    def _summary(self, draft: ChatDraft) -> str:'
    if marker in s:
        s = s.replace(marker, helper + marker)

# Add quality_warnings to plan draft responses before return in _draft_plan_with_llm.
old = """                    'weeks': weeks,\n                    'output': output,\n                })\n"""
new = """                    'weeks': weeks,\n                    'quality_warnings': self._plan_quality_warnings(weeks, plan_name),\n                    'output': output,\n                })\n"""
if old in s and 'quality_warnings' not in s[s.find('def _draft_plan_with_llm'):s.find('def _fallback_weeks')]:
    s = s.replace(old, new, 1)

# Add quality warnings to fallback branch too.
old = """            'weeks': weeks,\n            'output': output,\n        })\n"""
new = """            'weeks': weeks,\n            'quality_warnings': self._plan_quality_warnings(weeks, fallback_name),\n            'output': output,\n        })\n"""
# Replace later occurrence only if not already.
if old in s and 'quality_warnings' not in s[s.rfind("return ChatDraft(str(uuid.uuid4()), 'create_plan_from_draft'"):]:
    s = s.replace(old, new, 1)

# Summary should show schedule_preview and warnings, ignore quality_warnings raw list.
if "if k == 'quality_warnings'" not in s:
    old = """        for k, v in draft.args.items():\n            if k == 'schedule_preview' and isinstance(v, list):\n"""
    new = """        for k, v in draft.args.items():\n            if k == 'quality_warnings' and isinstance(v, list) and v:\n                lines.append('- quality warning: ' + '; '.join(str(x) for x in v))\n            elif k == 'schedule_preview' and isinstance(v, list):\n"""
    if old in s:
        s = s.replace(old, new)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 4) Chat UI: show quality warnings; make Add Intern schedule preview editable.
# -----------------------------------------------------------------------------
h = chat_html.read_text(encoding='utf-8')

# Show quality warnings in proposal card.
old = """  if(args.main_title) html += `<p><b>Main project:</b> ${escapeHtml(args.main_title)}</p>`;\n"""
new = """  if(args.quality_warnings && Array.isArray(args.quality_warnings) && args.quality_warnings.length){ html += `<div class=\"missing\"><b>Quality warning:</b><ul>${args.quality_warnings.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul><span class=\"hint\">Please edit or regenerate before using this plan for interns.</span></div>`; }\n  if(args.main_title) html += `<p><b>Main project:</b> ${escapeHtml(args.main_title)}</p>`;\n"""
if old in h and 'Quality warning:' not in h:
    h = h.replace(old, new)

# Replace read-only schedule preview in edit area with editable fields if existing read-only block present.
old = """    if(args.schedule_preview && Array.isArray(args.schedule_preview)){\n      html += '<h3>Schedule Preview</h3><p class=\"hint\">Daily tasks and weekly projects are generated from the selected plan and dates. To change these, edit the selected plan before approval or change the plan name.</p>';\n      args.schedule_preview.forEach(w=>{ html += `<div class=\"week-edit\"><h4>Week ${escapeHtml(w.week)} (${escapeHtml(w.date_range)})</h4><p><b>Theme:</b> ${escapeHtml(w.theme)}</p><p><b>Daily task:</b> ${escapeHtml(w.daily_task)}</p><p><b>Weekly project:</b> ${escapeHtml(w.weekly_project)}</p></div>`; });\n    }\n"""
new = """    if(args.schedule_preview && Array.isArray(args.schedule_preview)){\n      html += '<h3>Editable Schedule Preview</h3><p class=\"hint\">Edit weekly theme, daily task, weekly project, and notes before approval. These edited values will be used to create the intern sheet.</p>';\n      args.schedule_preview.forEach((w,i)=>{\n        html += `<div class=\"week-edit edit_schedule_box\" data-week-index=\"${i}\"><h4>Week ${escapeHtml(w.week)} (${escapeHtml(w.date_range || '')})</h4>`;\n        html += `<label>Theme<input class=\"edit_schedule_theme\" value=\"${escapeHtml(w.theme || '')}\" /></label>`;\n        html += `<label>Daily task<textarea class=\"edit_schedule_task\">${escapeHtml(w.daily_task || '')}</textarea></label>`;\n        html += `<label>Weekly project<textarea class=\"edit_schedule_project\">${escapeHtml(w.weekly_project || '')}</textarea></label>`;\n        html += `<label>Notes<textarea class=\"edit_schedule_notes\">${escapeHtml(w.notes || '')}</textarea></label>`;\n        html += `</div>`;\n      });\n    }\n"""
if old in h:
    h = h.replace(old, new)

# Save edited schedule_preview for add_intern_with_plan.
old = """  } else if(cmd === 'add_intern_with_plan'){\n    ['name','plan_name','start_date','end_date','manager','skip_manager','main_title','objective','tech_stack','scenario','skills','deliverable'].forEach(k=>{\n      const el = document.getElementById('edit_' + k);\n      if(el) args[k] = el.value;\n    });\n  } else {\n"""
new = """  } else if(cmd === 'add_intern_with_plan'){\n    ['name','plan_name','start_date','end_date','manager','skip_manager','main_title','objective','tech_stack','scenario','skills','deliverable'].forEach(k=>{\n      const el = document.getElementById('edit_' + k);\n      if(el) args[k] = el.value;\n    });\n    const sched = document.querySelectorAll('.edit_schedule_box');\n    if(sched.length){\n      args.schedule_preview = Array.from(sched).map((box, i)=>({\n        week: i + 1,\n        date_range: (activeProposal.args.schedule_preview && activeProposal.args.schedule_preview[i] ? activeProposal.args.schedule_preview[i].date_range : ''),\n        theme: box.querySelector('.edit_schedule_theme')?.value || '',\n        daily_task: box.querySelector('.edit_schedule_task')?.value || '',\n        weekly_project: box.querySelector('.edit_schedule_project')?.value || '',\n        notes: box.querySelector('.edit_schedule_notes')?.value || ''\n      }));\n    }\n  } else {\n"""
if old in h:
    h = h.replace(old, new)

chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.37 Plan quality and Add Intern editable schedule preview

- Removes internal fallback/debug text from visible Excel fields, including `LLM returned no detailed weeks; generated safe draft.`
- Adds plan quality warnings to chat proposals when generated weeks look generic, short, or fallback-based.
- Add Intern With Plan now supports edited `schedule_preview` values during approval.
- The Edit button for Add Intern With Plan now lets users edit week theme, daily task, weekly project, and notes before workbook creation.
- The approved workbook uses the edited preview if present.
''', encoding='utf-8')

print('v0.37 plan quality + intern editable schedule preview patch applied successfully.')
