from pathlib import Path

root = Path(__file__).resolve().parent
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run this patch inside intern_tracker_system_v0.')

h = chat_html.read_text(encoding='utf-8')

# v0.53: Fix Create Plan edit/save flow.
# Cause: newer v41 UI renders plan weeks as .week-card, while the older saveEditedDraft
# function only collected .week-edit. That sent weeks=[] to /api/chat/update, so backend
# asked for missing "weeks" and the proposal got stuck.

override = r'''

// v0.53 robust Save Draft override for Create Plan and Add Intern With Plan
async function saveEditedDraft(){
  if(!activeProposal || !activeDraftId) return;
  const cmd = activeProposal.command;
  let args = {};

  if(cmd === 'create_plan_from_draft'){
    const planNameEl = document.getElementById('edit_plan_name');
    const descEl = document.getElementById('edit_description');
    args.plan_name = planNameEl ? planNameEl.value : ((activeProposal.args || {}).plan_name || '');
    args.description = descEl ? descEl.value : ((activeProposal.args || {}).description || '');

    // Support both old editor class (.week-edit) and new v41 details class (.week-card).
    const weekBoxes = Array.from(document.querySelectorAll('.week-edit, .week-card')).filter(box =>
      box.querySelector('.edit_week_theme') || box.querySelector('.edit_week_task') || box.querySelector('.edit_week_project') || box.querySelector('.edit_week_notes')
    );

    args.weeks = weekBoxes.map((box, i)=>({
      week: i + 1,
      theme: box.querySelector('.edit_week_theme')?.value || '',
      task: box.querySelector('.edit_week_task')?.value || '',
      weekly_project: box.querySelector('.edit_week_project')?.value || '',
      notes: box.querySelector('.edit_week_notes')?.value || ''
    })).filter(w => w.theme || w.task || w.weekly_project || w.notes);

    // If no week boxes were found, keep the previous weeks instead of sending [] and triggering missing weeks.
    if(!args.weeks.length && activeProposal.args && Array.isArray(activeProposal.args.weeks)){
      args.weeks = activeProposal.args.weeks;
    }
  } else if(cmd === 'add_intern_with_plan'){
    ['name','plan_name','start_date','end_date','manager','skip_manager','main_title','objective','tech_stack','scenario','skills','deliverable'].forEach(k=>{
      const el = document.getElementById('edit_' + k);
      if(el) args[k] = el.value;
    });

    const sched = document.querySelectorAll('.edit_schedule_box');
    if(sched.length){
      args.schedule_preview = Array.from(sched).map((box, i)=>({
        week: i + 1,
        date_range: (activeProposal.args.schedule_preview && activeProposal.args.schedule_preview[i] ? activeProposal.args.schedule_preview[i].date_range : ''),
        theme: box.querySelector('.edit_schedule_theme')?.value || '',
        daily_task: (Array.from(box.querySelectorAll('.edit_schedule_day_task')).map(x=>x.value).filter(Boolean)[0] || box.querySelector('.edit_schedule_task')?.value || ''),
        daily_tasks: Array.from(box.querySelectorAll('.edit_schedule_day_task')).map(x=>x.value).filter(Boolean),
        weekly_project: box.querySelector('.edit_schedule_project')?.value || '',
        notes: box.querySelector('.edit_schedule_notes')?.value || ''
      }));
    }
  } else {
    document.querySelectorAll('[data-edit-key]').forEach(el=>{ args[el.dataset.editKey] = el.value; });
  }

  const res = await fetch('/api/chat/update', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({draft_id:activeDraftId,args})
  });
  const data = await res.json();
  handleChatResponse(data);
  chatAppend('assistant','Draft updated. Please review the updated proposal.');
}
'''

# Insert after existing scripts but before init() if possible, so this definition wins.
pos = h.rfind('init();')
if pos != -1:
    h = h[:pos] + override + '\n' + h[pos:]
else:
    h += '\n<script>\n' + override + '\n</script>\n'

chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.53 Fix Create Plan edit/save missing weeks

- Fixed issue where editing a generated plan and clicking Save Draft caused the assistant to ask for missing `weeks`.
- The newer proposal UI used `.week-card`, while the older save logic only read `.week-edit`.
- Save Draft now collects plan weeks from both layouts and preserves existing weeks if no week fields are found.
''', encoding='utf-8')

print('v0.53 fix plan edit/save missing weeks patch applied successfully.')
