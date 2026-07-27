from pathlib import Path

root = Path(__file__).resolve().parent
chat_service = root / 'tracker_chat' / 'chat_service.py'
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_service.exists():
    raise SystemExit('tracker_chat/chat_service.py not found. Run inside intern_tracker_system_v0.')
if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run inside intern_tracker_system_v0.')

# -----------------------------------------------------------------------------
# 1) Backend/chat: enrich extend_intern_with_plan proposal with extension preview
# -----------------------------------------------------------------------------
s = chat_service.read_text(encoding='utf-8')

if 'v0.60 extend intern with plan preview enrichment' not in s:
    s += r'''

# v0.60 extend intern with plan preview enrichment
# Shows the extension plan before approval. Does not change execution logic.
if not hasattr(ChatService, '_base_response_for_draft_v60'):
    ChatService._base_response_for_draft_v60 = ChatService._response_for_draft


def _v60_resolve_workbook(value: str):
    from pathlib import Path
    base = Path(__file__).resolve().parents[1]
    if not value:
        return value
    p = Path(value)
    if p.exists():
        return str(p)
    for folder in [base / 'outputs', base / 'uploads', base]:
        c = folder / Path(value).name
        if c.exists():
            return str(c)
    return value


def _v60_enrich_extend_with_plan(self, draft):
    if not draft or draft.command != 'extend_intern_with_plan':
        return
    args = draft.args
    required = ['source', 'intern', 'new_end', 'plan_name']
    if any(not args.get(k) for k in required):
        return
    if args.get('extension_schedule_preview'):
        return
    try:
        from datetime import datetime, timedelta
        from tracker_excel.renderer.parser import parse_workbook
        from tracker_chat.intern_sheet_drafter import InternSheetDrafter

        source_path = _v60_resolve_workbook(args.get('source'))
        data = parse_workbook(source_path)
        intern_obj = None
        for item in data.interns:
            if item.name.strip().lower() == str(args.get('intern')).strip().lower():
                intern_obj = item
                break
        if not intern_obj:
            return
        current_end = intern_obj.main_row[4] if len(intern_obj.main_row) > 4 else None
        if not isinstance(current_end, datetime):
            return
        new_end_dt = datetime.fromisoformat(str(args.get('new_end')))
        extension_start = current_end + timedelta(days=1)
        while extension_start.weekday() >= 5:
            extension_start += timedelta(days=1)
        if extension_start.date() > new_end_dt.date():
            return

        drafter = InternSheetDrafter()
        draft_sheet = drafter.draft(
            source_path,
            str(args.get('intern')),
            extension_start.strftime('%Y-%m-%d'),
            new_end_dt.strftime('%Y-%m-%d'),
            str(args.get('plan_name')),
        )
        main = draft_sheet.get('main_project') or {}
        scenario = draft_sheet.get('scenario') or {}
        weeks = draft_sheet.get('weeks') or []

        args['current_end'] = current_end.strftime('%Y-%m-%d')
        args['extension_start'] = extension_start.strftime('%Y-%m-%d')
        args['extension_main_title'] = main.get('title', '')
        args['extension_objective'] = main.get('objective', '')
        args['extension_tech_stack'] = main.get('tech_stack', '')
        args['extension_scenario'] = scenario.get('scenario', '')
        args['extension_skills'] = scenario.get('skills', '')
        args['extension_deliverable'] = scenario.get('deliverable', '')
        args['extension_schedule_preview'] = weeks
    except Exception as e:
        args['extension_preview_error'] = str(e)


def _v60_response_for_draft(self, draft):
    _v60_enrich_extend_with_plan(self, draft)
    return ChatService._base_response_for_draft_v60(self, draft)

ChatService._response_for_draft = _v60_response_for_draft
'''

chat_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Frontend: render extension preview in professional proposal panel
# -----------------------------------------------------------------------------
h = chat_html.read_text(encoding='utf-8')

needle = "  } else if(data.command === 'create_plan_from_draft'){"
if needle in h and "data.command === 'extend_intern_with_plan'" not in h:
    extend_branch = r'''  } else if(data.command === 'extend_intern_with_plan'){
    body += `<div class="section-card"><h4>Extension Details</h4>${v41Rows(args, [['Intern','intern'],['Current end','current_end'],['Extension start','extension_start'],['New end','new_end'],['Extension plan','plan_name']])}</div>`;
    body += `<div class="section-card"><h4>Updated Main Project Focus</h4>${v41Rows(args, [['Title','extension_main_title'],['Objective','extension_objective'],['Tech stack','extension_tech_stack']])}</div>`;
    body += `<div class="section-card"><h4>Updated Scenario Focus</h4>${v41Rows(args, [['Scenario','extension_scenario'],['Skills','extension_skills'],['Deliverable','extension_deliverable']])}</div>`;
    if(args.extension_preview_error){
      body += `<div class="missing"><b>Preview warning:</b> ${v41Val(args.extension_preview_error)}</div>`;
    }
    if(args.extension_schedule_preview && Array.isArray(args.extension_schedule_preview)){
      body += `<div class="section-card"><h4>Extension Schedule Preview</h4><div class="hint">These are the new tasks/projects that will be added for the extension period only.</div>`;
      args.extension_schedule_preview.forEach((w, idx)=>{
        const daily = (w.daily_tasks && Array.isArray(w.daily_tasks)) ? w.daily_tasks : [w.daily_task || ''];
        body += `<details class="week-card" ${idx===0?'open':''}><summary>Extension Week ${v41Val(w.week)}: ${v41Val(w.theme)} <span class="hint">${v41Val(w.date_range || '')}</span></summary>`;
        body += `<ol class="day-list">${daily.map((d,i)=>`<li><b>Day ${i+1}:</b> ${v41Val(d)}</li>`).join('')}</ol>`;
        body += `<p><b>Weekly project:</b> ${v41Val(w.weekly_project)}</p>`;
        if(w.notes) body += `<p><b>Notes:</b> ${v41Val(w.notes)}</p>`;
        body += `</details>`;
      });
      body += `</div>`;
    }
'''
    h = h.replace(needle, extend_branch + needle, 1)

chat_html.write_text(h, encoding='utf-8')

# Compile check chat_service.
try:
    import py_compile
    py_compile.compile(str(chat_service), doraise=True)
except Exception as e:
    raise SystemExit(f'chat_service.py compile failed after v0.60 patch: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.60 Extend Intern With Plan preview

- Extend Intern With Plan proposals now show the generated extension plan before approval:
  - current end date
  - extension start date
  - new end date
  - extension plan
  - updated main project focus
  - updated scenario focus
  - extension weekly schedule preview with progressive daily tasks
- This is a proposal/UI preview fix. Execution logic remains the existing `extend_intern_with_plan` flow.
''', encoding='utf-8')

print('v0.60 extend intern with plan preview patch applied successfully.')
