from pathlib import Path
import re

root = Path(__file__).resolve().parent
web_app = root / 'web_app.py'
web_dir = root / 'web'
index = web_dir / 'index.html'
chat = web_dir / 'chat.html'

if not web_app.exists():
    raise SystemExit('web_app.py not found. Run this patch inside intern_tracker_system_v0.')
if not index.exists():
    raise SystemExit('web/index.html not found. Run this patch inside intern_tracker_system_v0.')
web_dir.mkdir(exist_ok=True)

# 1) Add a dedicated /chat route.
s = web_app.read_text(encoding='utf-8')
if '@app.get("/chat"' not in s:
    route = r'''

@app.get("/chat", response_class=HTMLResponse)
def chat_page():
    return (BASE_DIR / "web" / "chat.html").read_text(encoding="utf-8")
'''
    marker = '@app.get("/", response_class=HTMLResponse)'
    if marker not in s:
        raise SystemExit('Could not find home route insertion point in web_app.py')
    s = s.replace(marker, route + '\n' + marker)
    web_app.write_text(s, encoding='utf-8')

# 2) Remove old embedded chat sidebar from index page and add a clear link to chat page.
s = index.read_text(encoding='utf-8')
s = s.replace('main { display:grid; grid-template-columns: 290px 1fr 360px; gap:20px; padding:20px; }', 'main { display:grid; grid-template-columns: 290px 1fr; gap:20px; padding:20px; }')
# Remove old chat aside block if present.
s = re.sub(r'\n\s*<aside class="card"[^>]*>\s*<h2>Chat Assistant</h2>.*?</aside>\s*\n</main>', '\n</main>', s, flags=re.S)
# Add link to the dedicated chat page under header intro if not already added.
if 'Open Chat Assistant' not in s:
    s = s.replace('<p>Button/form interface over the same command engine used by CLI and future LLM chat.</p>', '<p>Button/form interface over the same command engine used by CLI and future LLM chat.</p>\n  <p><a href="/chat" style="color:white; font-weight:700; text-decoration:underline;">Open Chat Assistant</a></p>')
index.write_text(s, encoding='utf-8')

# 3) Add the new dedicated chat page.
chat.write_text(r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Intern Tracker Chat Assistant</title>
  <style>
    :root { --blue:#305496; --light:#f4f6fb; --border:#d9e2ef; --text:#1f2937; --muted:#64748b; --assistant:#ffffff; --user:#dbeafe; --ok:#166534; --bad:#991b1b; }
    * { box-sizing:border-box; }
    body { margin:0; font-family: Arial, sans-serif; background:var(--light); color:var(--text); }
    header { background:var(--blue); color:white; padding:18px 28px; display:flex; justify-content:space-between; align-items:center; gap:16px; }
    header h1 { margin:0; font-size:22px; }
    header a { color:white; font-weight:700; }
    main { max-width:1100px; margin:0 auto; padding:18px; display:grid; grid-template-columns: 1fr 320px; gap:18px; }
    .panel { background:white; border:1px solid var(--border); border-radius:16px; box-shadow:0 4px 18px rgba(15,23,42,.07); }
    .chat-shell { min-height:78vh; display:flex; flex-direction:column; overflow:hidden; }
    .chat-top { padding:14px 18px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; gap:12px; align-items:center; }
    .chat-top .small { color:var(--muted); font-size:13px; }
    #chatLog { flex:1; padding:18px; overflow:auto; background:linear-gradient(#f8fafc,#f4f6fb); }
    .msg { max-width:78%; margin:10px 0; padding:12px 14px; border-radius:16px; border:1px solid var(--border); line-height:1.45; white-space:pre-wrap; }
    .msg.user { margin-left:auto; background:var(--user); border-bottom-right-radius:6px; }
    .msg.assistant { margin-right:auto; background:var(--assistant); border-bottom-left-radius:6px; }
    .msg.system { margin:10px auto; background:#fff7ed; color:#9a3412; max-width:92%; }
    .composer { padding:14px; border-top:1px solid var(--border); background:white; display:flex; gap:10px; align-items:flex-end; }
    textarea { flex:1; min-height:58px; max-height:160px; resize:vertical; padding:12px; border:1px solid var(--border); border-radius:12px; font:inherit; }
    button { border:1px solid var(--border); border-radius:11px; padding:10px 14px; font-weight:700; cursor:pointer; background:white; }
    button.primary { background:var(--blue); color:white; border-color:var(--blue); }
    button.success { background:#16a34a; color:white; border-color:#16a34a; }
    button.danger { background:#fee2e2; color:#991b1b; border-color:#fecaca; }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .side { padding:16px; height:max-content; position:sticky; top:16px; }
    .side h2 { margin-top:0; font-size:18px; }
    .current { padding:10px; background:#eef2ff; border:1px solid #c7d2fe; border-radius:12px; word-break:break-word; }
    .hint { color:var(--muted); font-size:13px; line-height:1.45; }
    .proposal { border:1px solid #bfdbfe; background:#eff6ff; border-radius:14px; padding:12px; margin-top:8px; }
    .proposal h3 { margin:0 0 8px; color:#1d4ed8; }
    .proposal ul { margin:8px 0 0 20px; padding:0; }
    .proposal li { margin:5px 0; }
    .proposal-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
    .missing { margin-top:10px; padding:10px; border:1px dashed #f59e0b; background:#fffbeb; border-radius:12px; }
    label { display:flex; flex-direction:column; gap:5px; margin:8px 0; font-weight:700; font-size:13px; }
    input { padding:9px; border:1px solid var(--border); border-radius:9px; }
    .examples { display:flex; flex-direction:column; gap:8px; }
    .example { text-align:left; font-weight:500; padding:9px; border-radius:10px; }
    .status-ok { color:var(--ok); font-weight:700; }
    .status-bad { color:var(--bad); font-weight:700; }
    .download { margin-top:8px; }
    .download a { color:#1d4ed8; font-weight:700; }
  </style>
</head>
<body>
<header>
  <div>
    <h1>Intern Tracker Chat Assistant</h1>
    <div style="font-size:13px; opacity:.9;">Draft, review, approve, then execute. The assistant does not execute without approval.</div>
  </div>
  <a href="/">Back to Forms</a>
</header>
<main>
  <section class="panel chat-shell">
    <div class="chat-top">
      <div>
        <b>Conversation</b>
        <div class="small">The assistant will ask for missing info and show a clean proposal.</div>
      </div>
      <div id="approvalState" class="small">No active proposal</div>
    </div>
    <div id="chatLog"></div>
    <div class="composer">
      <textarea id="chatInput" placeholder="Example: create an 8 week OpenShift plan for beginner interns with weekly projects"></textarea>
      <button class="primary" onclick="sendChat()">Send</button>
    </div>
  </section>

  <aside class="panel side">
    <h2>Current Workbook</h2>
    <div class="current" id="currentWorkbook">None selected</div>
    <p class="hint">The chat uses the current workbook from the forms page. If the wrong workbook shows here, go back to Forms, upload/select the correct workbook, then return here.</p>
    <button onclick="clearCurrent()">Clear Current Workbook</button>

    <h2 style="margin-top:22px;">Try</h2>
    <div class="examples">
      <button class="example" onclick="useExample('create an 8 week OpenShift plan for beginner interns with weekly projects')">Create OpenShift plan</button>
      <button class="example" onclick="useExample('add intern named Musab Khan from 2026-08-01 to 2026-09-30')">Add intern</button>
      <button class="example" onclick="useExample('apply plan OpenShift Foundation to intern Musab Khan')">Apply plan to intern</button>
      <button class="example" onclick="useExample('add holiday Company Holiday on 2026-08-14')">Add holiday</button>
      <button class="example" onclick="useExample('generate progress summary')">Summary</button>
    </div>

    <h2 style="margin-top:22px;">Active Proposal</h2>
    <div id="proposalBox" class="hint">No proposal yet.</div>
  </aside>
</main>
<script>
let activeDraftId = null;
let activeDraftNeedsInfo = false;
let activeProposal = null;

function currentWorkbook(){ return localStorage.getItem('currentWorkbook') || ''; }
function setCurrentWorkbook(name){ if(name){ localStorage.setItem('currentWorkbook', name); document.getElementById('currentWorkbook').textContent = name; } }
function clearCurrent(){ localStorage.removeItem('currentWorkbook'); document.getElementById('currentWorkbook').textContent='None selected'; }
function init(){ const cw=currentWorkbook(); if(cw) document.getElementById('currentWorkbook').textContent=cw; chatAppend('assistant','Hi. Tell me what you want to do. I will prepare a proposal and wait for your approval.'); }
function useExample(text){ document.getElementById('chatInput').value=text; document.getElementById('chatInput').focus(); }
function escapeHtml(s){ return String(s ?? '').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function chatAppend(who, text, cls){ const box=document.getElementById('chatLog'); const div=document.createElement('div'); div.className='msg ' + (cls || who); div.innerHTML=escapeHtml(text); box.appendChild(div); box.scrollTop=box.scrollHeight; }
function renderProposal(data){
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
function humanSummary(data){
  const cmd = data.command;
  const args = data.args || {};
  if(cmd === 'create_plan_from_draft') return `I drafted a ${args.weeks?.length || ''}-week plan and can create it in the current workbook.`;
  if(cmd === 'add_intern_basic') return `I can add ${args.name || 'the intern'} from ${args.start_date || 'start date'} to ${args.end_date || 'end date'}.`;
  if(cmd === 'apply_plan_to_intern') return `I can apply ${args.plan_name || 'the selected plan'} to ${args.intern || 'the intern'}.`;
  if(cmd === 'add_holiday') return `I can add the holiday ${args.name || ''} on ${args.date || ''}.`;
  if(cmd === 'extend_intern') return `I can extend ${args.intern || 'the intern'} to ${args.new_end || 'the new end date'}.`;
  if(cmd === 'summary') return `I can generate a progress summary for the current workbook.`;
  return data.label ? `I prepared ${data.label}.` : 'I prepared a proposal.';
}
async function sendChat(){
  const msg=document.getElementById('chatInput').value.trim();
  if(!msg) return;
  const lower=msg.toLowerCase();
  if(activeDraftId && ['approve','approved','yes','confirm','ok'].includes(lower)){ document.getElementById('chatInput').value=''; chatAppend('user', msg); await approveChat(); return; }
  if(activeDraftId && ['cancel','stop'].includes(lower)){ document.getElementById('chatInput').value=''; chatAppend('user', msg); await cancelChat(); return; }
  chatAppend('user', msg);
  document.getElementById('chatInput').value='';
  const url = activeDraftId && activeDraftNeedsInfo ? '/api/chat/fill' : '/api/chat/message';
  const body = activeDraftId && activeDraftNeedsInfo ? {draft_id:activeDraftId, message:msg} : {message:msg, current_workbook:currentWorkbook()};
  const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await res.json();
  handleChatResponse(data);
}
function handleChatResponse(data){
  if(!data.ok){ chatAppend('assistant', data.error || 'Something went wrong.', 'system'); return; }
  activeDraftId=data.draft_id;
  activeDraftNeedsInfo = data.type === 'needs_more_info';
  if(data.type === 'needs_more_info'){
    document.getElementById('approvalState').textContent = 'Needs more info';
    chatAppend('assistant', data.message || 'I need more information.');
    renderMissing(data);
    return;
  }
  document.getElementById('missingFields')?.remove();
  renderProposal(data);
}
function renderMissing(data){
  let old=document.getElementById('missingFields'); if(old) old.remove();
  const area=document.createElement('div'); area.id='missingFields'; area.className='missing';
  area.innerHTML='<b>Missing information</b>';
  (data.missing||[]).forEach(k=>{ area.innerHTML += `<label>${escapeHtml(k)}<input name="${escapeHtml(k)}" /></label>`; });
  area.innerHTML += '<button class="primary" onclick="submitMissing()">Update proposal</button>';
  document.getElementById('proposalBox').innerHTML='';
  document.getElementById('proposalBox').appendChild(area);
}
async function submitMissing(){
  const inputs=document.querySelectorAll('#missingFields input'); const args={}; inputs.forEach(i=>args[i.name]=i.value);
  const res=await fetch('/api/chat/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:activeDraftId,args})});
  const data=await res.json(); handleChatResponse(data);
}
async function approveChat(){
  if(!activeDraftId) return;
  document.getElementById('approvalState').textContent = 'Executing...';
  const res=await fetch('/api/chat/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:activeDraftId})});
  const data=await res.json();
  if(data.ok){
    chatAppend('assistant', data.message || 'Done.');
    if(data.output_path){ const fn=data.output_path.split(/[\\/]/).pop(); setCurrentWorkbook(fn); chatAppend('assistant', `Output saved as ${fn}.`); }
    if(data.download){ document.getElementById('proposalBox').innerHTML = `<div class="proposal"><h3 class="status-ok">Done</h3><p>${escapeHtml(data.message || 'Completed.')}</p><div class="download"><a href="${data.download}">Download output workbook</a></div></div>`; }
  } else {
    chatAppend('assistant', data.message || data.error || 'The action failed.', 'system');
    document.getElementById('proposalBox').innerHTML = `<div class="proposal"><h3 class="status-bad">Could not complete</h3><p>${escapeHtml(data.message || data.error || 'The action failed.')}</p></div>`;
  }
  activeDraftId=null; activeDraftNeedsInfo=false; activeProposal=null; document.getElementById('approvalState').textContent='No active proposal';
}
async function cancelChat(){
  if(activeDraftId){ await fetch('/api/chat/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:activeDraftId})}); }
  activeDraftId=null; activeDraftNeedsInfo=false; activeProposal=null; document.getElementById('approvalState').textContent='No active proposal'; document.getElementById('proposalBox').innerHTML='No proposal yet.'; chatAppend('assistant','Cancelled.');
}
init();
</script>
</body>
</html>
''', encoding='utf-8')

# README note
readme = root / 'README.md'
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.19 Separate chat page and clean chat UX

- Chat Assistant moved to `/chat`.
- Main forms page now links to the chat page instead of embedding chat beside forms.
- Chat responses are now shown as message bubbles and proposal cards.
- Raw command JSON is hidden from the user.
- Approval results are shown as human-readable messages with download links.
''', encoding='utf-8')

print('v0.19 separate chat page + clean chat UI applied successfully.')
