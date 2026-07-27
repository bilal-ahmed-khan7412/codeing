from pathlib import Path

root = Path(__file__).resolve().parent
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Run this patch inside intern_tracker_system_v0.')

h = chat_html.read_text(encoding='utf-8')

css = r'''

/* v0.41 Professional chat/proposal layout */
body { overflow: hidden; }
main {
  max-width: none !important;
  height: calc(100vh - 74px);
  padding: 16px !important;
  display: grid !important;
  grid-template-columns: minmax(420px, 1fr) minmax(420px, 520px) !important;
  gap: 16px !important;
  overflow: hidden;
}
.chat-shell { height: calc(100vh - 106px); min-height: 0 !important; }
#chatLog { min-height: 0; }
.side {
  height: calc(100vh - 106px) !important;
  top: 16px !important;
  overflow: hidden !important;
  display: flex;
  flex-direction: column;
  padding: 0 !important;
}
.side > h2, .side > p, .side > label, .side > .file-row, .side > .examples, .side > #uploadStatus, .side > .current, .side > button {
  margin-left: 16px;
  margin-right: 16px;
}
.side > h2:first-child { margin-top: 16px; }
#proposalBox {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0 16px 16px;
}
.proposal {
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 100%;
  padding: 0 !important;
  overflow: hidden !important;
}
.proposal-header {
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--border);
  background: #eff6ff;
}
.proposal-header h3 { margin: 0 0 6px; }
.proposal-body {
  padding: 12px 14px;
  overflow: auto;
  min-height: 0;
}
.proposal-footer {
  position: sticky;
  bottom: 0;
  background: white;
  border-top: 1px solid var(--border);
  padding: 12px 14px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  z-index: 4;
}
.section-card {
  border: 1px solid var(--border);
  background: white;
  border-radius: 12px;
  padding: 12px;
  margin: 10px 0;
}
.section-card h4 { margin: 0 0 8px; color: #1d4ed8; }
.kv { display: grid; grid-template-columns: 130px 1fr; gap: 6px 10px; font-size: 13px; }
.kv b { color: #475569; }
details.week-card {
  border: 1px solid #dbeafe;
  background: #f8fbff;
  border-radius: 12px;
  padding: 10px 12px;
  margin: 10px 0;
}
details.week-card summary {
  cursor: pointer;
  font-weight: 700;
  color: #1d4ed8;
}
.day-list { margin: 8px 0 0 20px; padding: 0; }
.day-list li { margin: 6px 0; }
.edit-area {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  border: 0 !important;
  padding: 0 !important;
}
.edit-scroll {
  overflow: auto;
  min-height: 0;
  padding: 12px 14px;
}
.edit-footer {
  position: sticky;
  bottom: 0;
  background: white;
  border-top: 1px solid var(--border);
  padding: 12px 14px;
  display: flex;
  gap: 8px;
  z-index: 5;
}
.edit-area details {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 10px;
  margin: 10px 0;
  background: white;
}
.edit-area details summary { cursor: pointer; font-weight: 700; color: #1d4ed8; }
.edit-area textarea { min-height: 70px; }
@media (max-width: 980px) {
  body { overflow: auto; }
  main { height: auto; grid-template-columns: 1fr !important; overflow: visible; }
  .chat-shell, .side { height: auto !important; max-height: none; position: static !important; }
  #proposalBox { min-height: 360px; }
}
'''
if 'v0.41 Professional chat/proposal layout' not in h:
    h = h.replace('</style>', css + '\n  </style>')

override_js = r'''

// v0.41 professional proposal/review/edit panel overrides
function v41CleanLabel(data){
  if(data.command === 'create_plan_from_draft') return 'Create AI-Drafted Plan';
  if(data.command === 'add_intern_with_plan') return 'Add Intern With Plan';
  return data.label || data.command || 'Proposal';
}
function v41Val(v){ return escapeHtml(v || ''); }
function v41Rows(obj, keys){
  return '<div class="kv">' + keys.map(([label,key]) => `<b>${v41Val(label)}</b><span>${v41Val(obj[key])}</span>`).join('') + '</div>';
}
function v41ProposalHeader(title, summary){
  return `<div class="proposal-header"><h3>${v41Val(title)}</h3><div class="hint">${v41Val(summary)}</div></div>`;
}
function renderProposal(data){
  activeProposal = data;
  activeDraftId = data.draft_id;
  activeDraftNeedsInfo = false;
  document.getElementById('approvalState').textContent = 'Waiting for approval';
  const args = data.args || {};
  const title = v41CleanLabel(data);
  const summary = humanSummary(data);
  let body = '';

  if(data.command === 'add_intern_with_plan'){
    body += `<div class="section-card"><h4>Intern Details</h4>${v41Rows(args, [['Intern','name'],['Plan','plan_name'],['Start','start_date'],['End','end_date'],['Manager','manager'],['Skip manager','skip_manager']])}</div>`;
    body += `<div class="section-card"><h4>Main Project</h4>${v41Rows(args, [['Title','main_title'],['Objective','objective'],['Tech stack','tech_stack']])}</div>`;
    body += `<div class="section-card"><h4>Real-World Scenario</h4>${v41Rows(args, [['Scenario','scenario'],['Skills','skills'],['Deliverable','deliverable']])}</div>`;
    if(args.schedule_preview && Array.isArray(args.schedule_preview)){
      body += `<div class="section-card"><h4>Weekly Schedule Preview</h4><div class="hint">Expand weeks to review daily tasks and weekly projects.</div>`;
      args.schedule_preview.forEach((w, idx)=>{
        const daily = (w.daily_tasks && Array.isArray(w.daily_tasks)) ? w.daily_tasks : [w.daily_task || ''];
        body += `<details class="week-card" ${idx===0?'open':''}><summary>Week ${v41Val(w.week)}: ${v41Val(w.theme)} <span class="hint">${v41Val(w.date_range || '')}</span></summary>`;
        body += `<ol class="day-list">${daily.map((d,i)=>`<li><b>Day ${i+1}:</b> ${v41Val(d)}</li>`).join('')}</ol>`;
        body += `<p><b>Weekly project:</b> ${v41Val(w.weekly_project)}</p>`;
        if(w.notes) body += `<p><b>Notes:</b> ${v41Val(w.notes)}</p>`;
        body += `</details>`;
      });
      body += `</div>`;
    }
  } else if(data.command === 'create_plan_from_draft'){
    body += `<div class="section-card"><h4>Plan Details</h4>${v41Rows(args, [['Plan','plan_name'],['Description','description']])}</div>`;
    if(args.quality_warnings && Array.isArray(args.quality_warnings) && args.quality_warnings.length){
      body += `<div class="missing"><b>Quality warning</b><ul>${args.quality_warnings.map(x=>`<li>${v41Val(x)}</li>`).join('')}</ul></div>`;
    }
    if(args.weeks && Array.isArray(args.weeks)){
      body += `<div class="section-card"><h4>Plan Weeks</h4>`;
      args.weeks.forEach((w, idx)=>{
        body += `<details class="week-card" ${idx===0?'open':''}><summary>Week ${v41Val(w.week)}: ${v41Val(w.theme)}</summary>`;
        body += `<p><b>Task:</b> ${v41Val(w.task || w.daily_task)}</p><p><b>Weekly project:</b> ${v41Val(w.weekly_project)}</p>`;
        if(w.notes) body += `<p><b>Notes:</b> ${v41Val(w.notes)}</p>`;
        body += `</details>`;
      });
      body += `</div>`;
    }
  } else {
    body += `<div class="section-card"><h4>Action Details</h4><div class="kv">${Object.keys(args).filter(k=>typeof args[k] !== 'object').map(k=>`<b>${v41Val(k)}</b><span>${v41Val(args[k])}</span>`).join('')}</div></div>`;
  }

  const html = `<div class="proposal">${v41ProposalHeader(title, summary)}<div class="proposal-body">${body}</div><div class="proposal-footer"><button class="success" onclick="approveChat()">Approve</button><button onclick="showEditDraft()">Edit</button><button class="danger" onclick="cancelChat()">Cancel</button></div></div>`;
  document.getElementById('proposalBox').innerHTML = html;
  chatAppend('assistant', summary + '\n\nReview the proposal on the right. You can approve, edit, or cancel.');
}
function showEditDraft(){
  if(!activeProposal || !activeDraftId) return;
  const args = activeProposal.args || {};
  const cmd = activeProposal.command;
  let body = '';
  if(cmd === 'add_intern_with_plan'){
    body += `<details open><summary>Intern Details</summary>`;
    body += `<label>Intern name<input id="edit_name" value="${v41Val(args.name)}" /></label>`;
    body += `<label>Plan name<input id="edit_plan_name" value="${v41Val(args.plan_name)}" /></label>`;
    body += `<label>Start date<input id="edit_start_date" value="${v41Val(args.start_date)}" /></label>`;
    body += `<label>End date<input id="edit_end_date" value="${v41Val(args.end_date)}" /></label>`;
    body += `<label>Manager<input id="edit_manager" value="${v41Val(args.manager)}" /></label>`;
    body += `<label>Skip manager<input id="edit_skip_manager" value="${v41Val(args.skip_manager)}" /></label></details>`;
    body += `<details><summary>Main Project</summary><label>Title<input id="edit_main_title" value="${v41Val(args.main_title)}" /></label><label>Objective<textarea id="edit_objective">${v41Val(args.objective)}</textarea></label><label>Tech stack<input id="edit_tech_stack" value="${v41Val(args.tech_stack)}" /></label></details>`;
    body += `<details><summary>Real-World Scenario</summary><label>Scenario<textarea id="edit_scenario">${v41Val(args.scenario)}</textarea></label><label>Skills<input id="edit_skills" value="${v41Val(args.skills)}" /></label><label>Deliverable<textarea id="edit_deliverable">${v41Val(args.deliverable)}</textarea></label></details>`;
    if(args.schedule_preview && Array.isArray(args.schedule_preview)){
      body += `<details open><summary>Weekly Schedule</summary><div class="hint">Edit Day 1 to Day 5 tasks, weekly project, and notes.</div>`;
      args.schedule_preview.forEach((w,i)=>{
        const dayTasks = (w.daily_tasks && Array.isArray(w.daily_tasks) && w.daily_tasks.length) ? w.daily_tasks : [w.daily_task || ''];
        body += `<details class="week-card edit_schedule_box" data-week-index="${i}" ${i===0?'open':''}><summary>Week ${v41Val(w.week)}: ${v41Val(w.theme)}</summary>`;
        body += `<label>Theme<input class="edit_schedule_theme" value="${v41Val(w.theme)}" /></label>`;
        for(let d=0; d<5; d++) body += `<label>Day ${d+1}<textarea class="edit_schedule_day_task">${v41Val(dayTasks[d] || dayTasks[dayTasks.length-1] || '')}</textarea></label>`;
        body += `<label>Weekly project<textarea class="edit_schedule_project">${v41Val(w.weekly_project)}</textarea></label>`;
        body += `<label>Notes<textarea class="edit_schedule_notes">${v41Val(w.notes)}</textarea></label>`;
        body += `</details>`;
      });
      body += `</details>`;
    }
  } else if(cmd === 'create_plan_from_draft'){
    body += `<details open><summary>Plan Details</summary><label>Plan name<input id="edit_plan_name" value="${v41Val(args.plan_name)}" /></label><label>Description<textarea id="edit_description">${v41Val(args.description)}</textarea></label></details>`;
    if(args.weeks && Array.isArray(args.weeks)){
      body += `<details open><summary>Weeks</summary>`;
      args.weeks.forEach((w,i)=>{
        body += `<details class="week-card" data-week-index="${i}" ${i===0?'open':''}><summary>Week ${v41Val(w.week)}: ${v41Val(w.theme)}</summary>`;
        body += `<label>Theme<input class="edit_week_theme" value="${v41Val(w.theme)}" /></label>`;
        body += `<label>Task<textarea class="edit_week_task">${v41Val(w.task || w.daily_task)}</textarea></label>`;
        body += `<label>Weekly project<textarea class="edit_week_project">${v41Val(w.weekly_project)}</textarea></label>`;
        body += `<label>Notes<textarea class="edit_week_notes">${v41Val(w.notes)}</textarea></label>`;
        body += `</details>`;
      });
      body += `</details>`;
    }
  } else {
    body += Object.keys(args).filter(k=>typeof args[k] !== 'object').map(k=>`<label>${v41Val(k)}<input data-edit-key="${v41Val(k)}" value="${v41Val(args[k])}" /></label>`).join('');
  }
  document.getElementById('proposalBox').innerHTML = `<div class="proposal"><div class="proposal-header"><h3>Editing Draft</h3><div class="hint">Make changes, then save the draft. The workbook is not created until approval.</div></div><div class="proposal-body"><div class="edit-area"><div class="edit-scroll">${body}</div></div></div><div class="proposal-footer"><button class="primary" onclick="saveEditedDraft()">Save Draft</button><button onclick="renderProposal(activeProposal)">Cancel Edit</button></div></div>`;
}
'''

# Insert override just before final init(); use last occurrence to keep overrides active.
pos = h.rfind('init();')
if pos == -1:
    h += '\n<script>\n' + override_js + '\n</script>\n'
else:
    h = h[:pos] + override_js + '\n' + h[pos:]

chat_html.write_text(h, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.41 Professional chat proposal panel

- Chat page now uses a more professional two-column layout.
- Proposal panel is sticky and scrolls internally.
- Approve/Edit/Cancel buttons stay visible in a sticky footer.
- Edit mode replaces the proposal panel instead of dumping a giant form below messages.
- Edit mode uses collapsible sections for intern details, main project, scenario, and weekly schedule.
''', encoding='utf-8')

print('v0.41 professional chat proposal layout patch applied successfully.')
