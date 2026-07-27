from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run this patch inside intern_tracker_system_v0 after v0.23+.')
if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run this patch inside intern_tracker_system_v0 after v0.19+.')

# -----------------------------------------------------------------------------
# 1) Backend chat: enrich Add Intern With Plan proposals before approval
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

# Add imports for preview generation.
if 'from datetime import datetime, timedelta' not in s:
    s = s.replace('from datetime import datetime', 'from datetime import datetime, timedelta')
if 'from tracker_excel.renderer.parser import parse_workbook' not in s:
    s = s.replace('from tracker_commands.executor import CommandExecutor', 'from tracker_commands.executor import CommandExecutor\nfrom tracker_excel.renderer.parser import parse_workbook')

# Call enrichment before rendering ready proposal.
old = """        draft.status = 'awaiting_approval'\n        draft.summary = self._summary(draft)\n"""
new = """        if draft.command == 'add_intern_with_plan':\n            self._enrich_add_intern_with_plan(draft)\n        draft.status = 'awaiting_approval'\n        draft.summary = self._summary(draft)\n"""
if old in s and '_enrich_add_intern_with_plan(draft)' not in s:
    s = s.replace(old, new, 1)

# Add helper methods before _summary.
if 'def _enrich_add_intern_with_plan' not in s:
    helper = r'''
    def _enrich_add_intern_with_plan(self, draft: ChatDraft):
        """Populate preview and editable project/scenario fields for Add Intern With Plan.

        This does not create the workbook. It only enriches the in-memory draft so
        the user can review/edit before approval.
        """
        args = draft.args
        plan_name = (args.get('plan_name') or '').strip()
        source = args.get('source')
        start_date = args.get('start_date')
        end_date = args.get('end_date')
        if not plan_name:
            return

        # Topic-aware defaults come from PlanService when available.
        try:
            defaults = self.executor.plan_service._topic_defaults(plan_name)
        except Exception:
            defaults = {
                'project_title': f'{plan_name} Final Practical Demo',
                'objective': f'Complete a practical project aligned with the {plan_name} plan and document the outcome.',
                'tech_stack': plan_name,
                'scenario': f'A realistic work scenario aligned with {plan_name}.',
                'skills': plan_name,
                'deliverable': 'Working demo, notes, and final summary report.',
            }
        args.setdefault('main_title', defaults.get('project_title', ''))
        args.setdefault('objective', defaults.get('objective', ''))
        args.setdefault('tech_stack', defaults.get('tech_stack', ''))
        args.setdefault('scenario', defaults.get('scenario', ''))
        args.setdefault('skills', defaults.get('skills', ''))
        args.setdefault('deliverable', defaults.get('deliverable', ''))
        args.setdefault('final_project', args.get('main_title', ''))

        # Build a week-level preview from the selected plan and intern dates.
        try:
            data = parse_workbook(source)
            plan = self.executor.plan_service._find_plan(data, plan_name)
            if not plan:
                return
            start = datetime.fromisoformat(str(start_date))
            end = datetime.fromisoformat(str(end_date))
            week_dates = {}
            current = start
            workday = 0
            while current.date() <= end.date():
                if current.weekday() < 5:
                    workday += 1
                    week = ((workday - 1) // 5) + 1
                    week_dates.setdefault(week, []).append(current)
                current += timedelta(days=1)
            plan_rows = {}
            for row in plan.rows:
                try:
                    w = int(row[0])
                except Exception:
                    continue
                plan_rows[w] = row
            preview = []
            for week, dates in sorted(week_dates.items()):
                row = plan_rows.get(week, [])
                theme = row[1] if len(row) > 1 and row[1] else 'Learning Plan'
                task = row[2] if len(row) > 2 and row[2] else 'Task to be assigned'
                project = row[3] if len(row) > 3 and row[3] else f'Week {week}: Weekly Project'
                preview.append({
                    'week': week,
                    'date_range': f"{dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}",
                    'theme': theme,
                    'daily_task': task,
                    'weekly_project': project,
                })
            args['schedule_preview'] = preview
        except Exception:
            # Preview is helpful but should not block the proposal.
            return

'''
    marker = '    def _summary(self, draft: ChatDraft) -> str:'
    if marker not in s:
        raise SystemExit('Could not find _summary method insertion point in chat_service.py')
    s = s.replace(marker, helper + marker)

# Summary mention schedule preview for add_intern_with_plan.
old = """        for k, v in draft.args.items():\n            if k == 'weeks' and isinstance(v, list):\n"""
new = """        for k, v in draft.args.items():\n            if k == 'schedule_preview' and isinstance(v, list):\n                lines.append(f'- schedule preview: {len(v)} week(s) generated from selected plan and intern dates')\n                for item in v[:10]:\n                    if isinstance(item, dict):\n                        lines.append(f\"  - Week {item.get('week')} ({item.get('date_range')}): {item.get('theme')} | {item.get('weekly_project')}\")\n            elif k == 'weeks' and isinstance(v, list):\n"""
if old in s and "schedule preview" not in s:
    s = s.replace(old, new)

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Frontend chat: show Add Intern With Plan project/scenario/schedule preview
# -----------------------------------------------------------------------------
hs = chat_html.read_text(encoding='utf-8')

# Add schedule preview display in renderProposal after scenario line.
old = """  if(args.scenario) html += `<p><b>Scenario:</b> ${escapeHtml(args.scenario)}</p>`;\n  if(args.weeks && Array.isArray(args.weeks)){\n"""
new = """  if(args.scenario) html += `<p><b>Scenario:</b> ${escapeHtml(args.scenario)}</p>`;\n  if(args.schedule_preview && Array.isArray(args.schedule_preview)){\n    html += `<b>Schedule preview:</b><ul>`;\n    args.schedule_preview.forEach(w=>{ html += `<li>Week ${escapeHtml(w.week)} (${escapeHtml(w.date_range)}): ${escapeHtml(w.theme)}<br><span class=\"hint\">Daily task: ${escapeHtml(w.daily_task || '')}<br>Weekly project: ${escapeHtml(w.weekly_project || '')}</span></li>`; });\n    html += `</ul>`;\n  }\n  if(args.weeks && Array.isArray(args.weeks)){\n"""
if old in hs and 'Schedule preview:' not in hs:
    hs = hs.replace(old, new)

# Add schedule preview to edit form as read-only context for add_intern_with_plan.
old = """    html += `<label>Deliverable<textarea id="edit_deliverable">${escapeHtml(args.deliverable || '')}</textarea></label>`;\n  } else {\n"""
new = """    html += `<label>Deliverable<textarea id="edit_deliverable">${escapeHtml(args.deliverable || '')}</textarea></label>`;\n    if(args.schedule_preview && Array.isArray(args.schedule_preview)){\n      html += '<h3>Schedule Preview</h3><p class=\"hint\">Daily tasks and weekly projects are generated from the selected plan and dates. To change these, edit the selected plan before approval or change the plan name.</p>';\n      args.schedule_preview.forEach(w=>{ html += `<div class=\"week-edit\"><h4>Week ${escapeHtml(w.week)} (${escapeHtml(w.date_range)})</h4><p><b>Theme:</b> ${escapeHtml(w.theme)}</p><p><b>Daily task:</b> ${escapeHtml(w.daily_task)}</p><p><b>Weekly project:</b> ${escapeHtml(w.weekly_project)}</p></div>`; });\n    }\n  } else {\n"""
if old in hs and 'Daily tasks and weekly projects are generated' not in hs:
    hs = hs.replace(old, new)

chat_html.write_text(hs, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) README note
# -----------------------------------------------------------------------------
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.28 Add Intern With Plan preview enrichment

- Add Intern With Plan proposals now show the generated information before approval:
  - Main project
  - Objective
  - Tech stack
  - Real-world scenario
  - Skills
  - Deliverable
  - Week-level schedule preview with date ranges, daily task, and weekly project
- The Edit button lets the user edit intern details and project/scenario fields before approval.
- Schedule preview is generated from the selected plan and intern dates. To change daily task/weekly project content, edit the plan before approval or select another plan.
''', encoding='utf-8')

print('v0.28 Add Intern With Plan preview enrichment patch applied successfully.')
