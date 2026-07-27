from pathlib import Path
import re

root = Path(__file__).resolve().parent
chat_html = root / 'web' / 'chat.html'
readme = root / 'README.md'

if not chat_html.exists():
    raise SystemExit('web/chat.html not found. Apply v0.19+ first, then run inside intern_tracker_system_v0.')

s = chat_html.read_text(encoding='utf-8')

# -----------------------------------------------------------------------------
# Add a little styling for editable draft sections.
# -----------------------------------------------------------------------------
if '.edit-area' not in s:
    s = s.replace(
        ".download a { color:#1d4ed8; font-weight:700; }",
        ".download a { color:#1d4ed8; font-weight:700; }\n    .edit-area { margin-top:12px; padding:12px; background:#ffffff; border:1px solid var(--border); border-radius:12px; }\n    .edit-area textarea { width:100%; min-height:74px; resize:vertical; }\n    .week-edit { border:1px solid #dbeafe; background:#f8fbff; border-radius:12px; padding:10px; margin:10px 0; }\n    .week-edit h4 { margin:0 0 8px; color:#1d4ed8; }\n    .two-col { display:grid; grid-template-columns:1fr 1fr; gap:10px; }\n    @media (max-width:900px){ main{grid-template-columns:1fr;} .two-col{grid-template-columns:1fr;} }"
    )

# -----------------------------------------------------------------------------
# Replace renderProposal function to include Edit button.
# -----------------------------------------------------------------------------
old_render = r'''function renderProposal(data){
  activeProposal = data;
  document.getElementById('approvalState').textContent = 'Waiting for approval';
  const args = data.args || {};
  let html = `<div class="proposal"><h3>${escapeHtml(data.label || data.command || 'Proposal')}</h3>`;
  html += `<p>${escapeHtml(humanSummary(data))}</p>`;
  if(args.plan_name) html += `<p><b>Plan:</b> ${escapeHtml(args.plan_name)}</p>`;
  if(args.name) html += `<p><b>Intern:</b> ${escapeHtml(args.name)}</p>`;
  if(args.intern) html += `<p><b>Intern:</b> ${escapeHtml(args.intern)}</p>`;
  if(args.start_date || args.end_date) html += `<p><b>Dates:</b> ${escapeHtml(args.start_date || '')} to ${escapeHtml(args.end_date || '')}</p>`;
  if(args.weeks && Array.isArray(args.weeks)){
    html += `<b>Drafted weeks:</b><ul>`;
    args.weeks.forEach(w=>{ html += `<li>Week ${escapeHtml(w.week)}: ${escapeHtml(w.theme)}<br><span class="hint">${escapeHtml(w.weekly_project || '')}</span></li>`; });
    html += `</ul>`;
  }
  html += `<div class="proposal-actions"><button class="success" onclick="approveChat()">Approve</button><button class="danger" onclick="cancelChat()">Cancel</button></div></div>`;
  document.getElementById('proposalBox').innerHTML = html;
  chatAppend('assistant', humanSummary(data) + '\n\nReview the proposal card on the right, then approve or cancel.');
}
'''
new_render = r'''function renderProposal(data){
  activeProposal = data;
  document.getElementById('approvalState').textContent = 'Waiting for approval';
  const args = data.args || {};
  let html = `<div class="proposal"><h3>${escapeHtml(cleanLabel(data))}</h3>`;
  html += `<p>${escapeHtml(humanSummary(data))}</p>`;
  if(args.plan_name) html += `<p><b>Plan:</b> ${escapeHtml(args.plan_name)}</p>`;
  if(args.name) html += `<p><b>Intern:</b> ${escapeHtml(args.name)}</p>`;
  if(args.intern) html += `<p><b>Intern:</b> ${escapeHtml(args.intern)}</p>`;
  if(args.start_date || args.end_date) html += `<p><b>Dates:</b> ${escapeHtml(args.start_date || '')} to ${escapeHtml(args.end_date || '')}</p>`;
  if(args.main_title) html += `<p><b>Main project:</b> ${escapeHtml(args.main_title)}</p>`;
  if(args.scenario) html += `<p><b>Scenario:</b> ${escapeHtml(args.scenario)}</p>`;
  if(args.weeks && Array.isArray(args.weeks)){
    html += `<b>Drafted weeks:</b><ul>`;
    args.weeks.forEach(w=>{ html += `<li>Week ${escapeHtml(w.week)}: ${escapeHtml(w.theme)}<br><span class="hint">${escapeHtml(w.weekly_project || '')}</span></li>`; });
    html += `</ul>`;
  }
  html += `<div class="proposal-actions"><button class="success" onclick="approveChat()">Approve</button><button onclick="showEditDraft()">Edit</button><button class="danger" onclick="cancelChat()">Cancel</button></div>`;
  html += `<div id="editDraftArea"></div></div>`;
  document.getElementById('proposalBox').innerHTML = html;
  chatAppend('assistant', humanSummary(data) + '\n\nReview the proposal card on the right. You can approve, edit, or cancel.');
}
'''
if old_render in s:
    s = s.replace(old_render, new_render)
elif 'function renderProposal(data)' in s and 'showEditDraft' not in s:
    print('Warning: renderProposal exact block not found. Edit button may need manual merge.')

# -----------------------------------------------------------------------------
# Add clean label + editable draft helpers before init();
# -----------------------------------------------------------------------------
if 'function showEditDraft()' not in s:
    helpers = r'''
function cleanLabel(data){
  if(data.command === 'create_plan_from_draft') return 'Create AI-Drafted Plan';
  if(data.command === 'add_intern_with_plan') return 'Add Intern With Plan';
  return data.label || data.command || 'Proposal';
}
function showEditDraft(){
  if(!activeProposal || !activeDraftId) return;
  const args = activeProposal.args || {};
  const cmd = activeProposal.command;
  let html = '<div class="edit-area"><h3>Edit Draft</h3>';
  if(cmd === 'create_plan_from_draft'){
    html += `<label>Plan name<input id="edit_plan_name" value="${escapeHtml(args.plan_name || '')}" /></label>`;
    html += `<label>Description<textarea id="edit_description">${escapeHtml(args.description || '')}</textarea></label>`;
    html += '<h3>Weeks</h3>';
    const weeks = Array.isArray(args.weeks) ? args.weeks : [];
    weeks.forEach((w, i)=>{
      html += `<div class="week-edit" data-week-index="${i}"><h4>Week ${escapeHtml(w.week || i+1)}</h4>`;
      html += `<label>Theme<input class="edit_week_theme" value="${escapeHtml(w.theme || '')}" /></label>`;
      html += `<label>Task<textarea class="edit_week_task">${escapeHtml(w.task || '')}</textarea></label>`;
      html += `<label>Weekly project<textarea class="edit_week_project">${escapeHtml(w.weekly_project || '')}</textarea></label>`;
      html += `<label>Notes<textarea class="edit_week_notes">${escapeHtml(w.notes || '')}</textarea></label>`;
      html += '</div>';
    });
  } else if(cmd === 'add_intern_with_plan'){
    html += '<div class="two-col">';
    html += `<label>Intern name<input id="edit_name" value="${escapeHtml(args.name || '')}" /></label>`;
    html += `<label>Plan name<input id="edit_plan_name" value="${escapeHtml(args.plan_name || '')}" /></label>`;
    html += `<label>Start date<input id="edit_start_date" value="${escapeHtml(args.start_date || '')}" /></label>`;
    html += `<label>End date<input id="edit_end_date" value="${escapeHtml(args.end_date || '')}" /></label>`;
    html += `<label>Manager<input id="edit_manager" value="${escapeHtml(args.manager || '')}" /></label>`;
    html += `<label>Skip manager<input id="edit_skip_manager" value="${escapeHtml(args.skip_manager || '')}" /></label>`;
    html += '</div>';
    html += `<label>Main project title<input id="edit_main_title" value="${escapeHtml(args.main_title || '')}" /></label>`;
    html += `<label>Objective<textarea id="edit_objective">${escapeHtml(args.objective || '')}</textarea></label>`;
    html += `<label>Tech stack<input id="edit_tech_stack" value="${escapeHtml(args.tech_stack || '')}" /></label>`;
    html += `<label>Scenario<textarea id="edit_scenario">${escapeHtml(args.scenario || '')}</textarea></label>`;
    html += `<label>Skills<input id="edit_skills" value="${escapeHtml(args.skills || '')}" /></label>`;
    html += `<label>Deliverable<textarea id="edit_deliverable">${escapeHtml(args.deliverable || '')}</textarea></label>`;
  } else {
    Object.keys(args).forEach(k=>{
      const v = args[k];
      if(Array.isArray(v) || typeof v === 'object') return;
      html += `<label>${escapeHtml(k)}<input data-edit-key="${escapeHtml(k)}" value="${escapeHtml(v || '')}" /></label>`;
    });
  }
  html += '<div class="proposal-actions"><button class="primary" onclick="saveEditedDraft()">Save Draft</button><button onclick="hideEditDraft()">Close</button></div></div>';
  document.getElementById('editDraftArea').innerHTML = html;
}
function hideEditDraft(){ const area=document.getElementById('editDraftArea'); if(area) area.innerHTML=''; }
async function saveEditedDraft(){
  if(!activeProposal || !activeDraftId) return;
  const cmd = activeProposal.command;
  let args = {};
  if(cmd === 'create_plan_from_draft'){
    args.plan_name = document.getElementById('edit_plan_name')?.value || '';
    args.description = document.getElementById('edit_description')?.value || '';
    const weekBoxes = document.querySelectorAll('.week-edit');
    args.weeks = Array.from(weekBoxes).map((box, i)=>({
      week: i + 1,
      theme: box.querySelector('.edit_week_theme')?.value || '',
      task: box.querySelector('.edit_week_task')?.value || '',
      weekly_project: box.querySelector('.edit_week_project')?.value || '',
      notes: box.querySelector('.edit_week_notes')?.value || ''
    }));
  } else if(cmd === 'add_intern_with_plan'){
    ['name','plan_name','start_date','end_date','manager','skip_manager','main_title','objective','tech_stack','scenario','skills','deliverable'].forEach(k=>{
      const el = document.getElementById('edit_' + k);
      if(el) args[k] = el.value;
    });
  } else {
    document.querySelectorAll('[data-edit-key]').forEach(el=>{ args[el.dataset.editKey] = el.value; });
  }
  const res=await fetch('/api/chat/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:activeDraftId,args})});
  const data=await res.json();
  handleChatResponse(data);
  chatAppend('assistant','Draft updated. Please review the updated proposal.');
}
'''
    s = s.replace('init();', helpers + '\ninit();')

chat_html.write_text(s, encoding='utf-8')

# README note.
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.26 Editable proposal cards

- Proposal cards now include Approve / Edit / Cancel.
- Create AI-Drafted Plan proposals can be edited before approval:
  - Plan name
  - Description
  - Week theme/task/weekly project/notes
- Add Intern With Plan proposals can be edited before approval:
  - Intern details
  - Plan name
  - Dates
  - Main project
  - Scenario
  - Skills and deliverable
- Save Draft updates the in-memory draft. The workbook is still created only after approval.
''', encoding='utf-8')

print('v0.26 editable proposal cards patch applied successfully.')
