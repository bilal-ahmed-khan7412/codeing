from pathlib import Path

root = Path(__file__).resolve().parent
logs = root / 'web' / 'logs.html'
readme = root / 'README.md'

if not logs.exists():
    raise SystemExit('web/logs.html not found. Run inside intern_tracker_system_v0 after governance add-on.')

html = r'''<!doctype html>
<html>
<head>
  <title>Activity Logs</title>
  <style>
  body{font-family:Arial,sans-serif;background:#f4f6fb;margin:0;color:#1f2937}
  header{background:#305496;color:white;padding:18px 28px;display:flex;justify-content:space-between;align-items:center}
  header a{color:white;font-weight:700;margin-left:14px}
  main{max-width:1200px;margin:0 auto;padding:20px}
  .card{background:white;border:1px solid #d9e2ef;border-radius:14px;padding:16px;box-shadow:0 4px 16px rgba(15,23,42,.06);margin-bottom:16px}
  input{padding:10px;border:1px solid #d9e2ef;border-radius:9px;font:inherit;width:100%;box-sizing:border-box}
  label{display:flex;flex-direction:column;gap:6px;font-weight:700;margin:8px 0}
  button{background:#305496;color:white;border:none;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}
  table{width:100%;border-collapse:collapse;background:white}
  th,td{border-bottom:1px solid #e5e7eb;text-align:left;padding:9px;font-size:13px;vertical-align:top}
  th{background:#eef2ff}
  .grid{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px}
  .muted{color:#64748b;font-size:13px}
  .error{color:#991b1b;font-weight:700}
  .empty{padding:18px;text-align:center;color:#64748b}
  .wrap{word-break:break-word;max-width:220px}
  .nav a{color:white}
  @media(max-width:900px){.grid{grid-template-columns:1fr}table{font-size:12px}}
  </style>
</head>
<body>
<header>
  <h2>Activity Logs</h2>
  <div class="nav"><a href="/">Forms</a><a href="/chat">Chat</a><a href="/users">Users</a><a href="/tasks">Tasks</a><a href="/logout">Logout</a></div>
</header>
<main>
  <div class="card">
    <h3>Filters</h3>
    <p class="muted">Shows login/logout, user actions, chat approvals, command execution, failures, and task tracking activity.</p>
    <div class="grid">
      <label>Search<input id="filter_q" placeholder="intern, plan, workbook, summary"></label>
      <label>Email<input id="filter_email" placeholder="user email"></label>
      <label>Action<input id="filter_action" placeholder="Login, Add Intern, Create Plan"></label>
      <label>Status<input id="filter_status" placeholder="Success, Failed, Blocked"></label>
    </div>
    <button onclick="loadLogs()">Apply</button>
    <button onclick="clearFilters()">Clear</button>
    <a href="/api/logs/export"><button>Export CSV</button></a>
    <span id="logStatus" class="muted"></span>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Time</th><th>User</th><th>Role</th><th>Interface</th><th>Action</th><th>Target</th><th>Status</th><th>Approval</th><th>Output</th><th>Summary / Error</th></tr></thead>
      <tbody id="logRows"><tr><td colspan="10" class="empty">Loading logs...</td></tr></tbody>
    </table>
  </div>
</main>
<script>
function esc(v){return String(v ?? '').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));}
function val(id){return document.getElementById(id).value || '';}
async function loadLogs(){
  const statusEl = document.getElementById('logStatus');
  const rowsEl = document.getElementById('logRows');
  statusEl.textContent = ' Loading...';
  rowsEl.innerHTML = '<tr><td colspan="10" class="empty">Loading logs...</td></tr>';
  const params = new URLSearchParams({q: val('filter_q'), email: val('filter_email'), action: val('filter_action'), status: val('filter_status')});
  try {
    const r = await fetch('/api/logs?' + params.toString());
    const d = await r.json();
    if(!d.ok) { rowsEl.innerHTML = `<tr><td colspan="10" class="error">${esc(d.error || 'Could not load logs')}</td></tr>`; statusEl.textContent=''; return; }
    const logItems = d.logs || [];
    statusEl.textContent = ` ${logItems.length} log(s)`;
    if(!logItems.length) { rowsEl.innerHTML = '<tr><td colspan="10" class="empty">No logs found.</td></tr>'; return; }
    rowsEl.innerHTML = logItems.map(x=>`<tr>
      <td>${esc(x.timestamp)}</td>
      <td>${esc(x.user_name || x.email || '')}<br><span class="muted">${esc(x.email || '')}</span></td>
      <td>${esc(x.role || '')}</td>
      <td>${esc(x.interface || '')}</td>
      <td>${esc(x.action || '')}</td>
      <td class="wrap">${esc(x.target_name || '')}</td>
      <td>${esc(x.status || '')}</td>
      <td>${esc(x.approval_status || '')}</td>
      <td class="wrap">${esc(x.output_workbook || '')}</td>
      <td class="wrap">${esc(x.summary || x.error_message || '')}</td>
    </tr>`).join('');
  } catch(e) {
    rowsEl.innerHTML = `<tr><td colspan="10" class="error">JavaScript/API error: ${esc(e.message)}</td></tr>`;
    statusEl.textContent='';
  }
}
function clearFilters(){['filter_q','filter_email','filter_action','filter_status'].forEach(id=>document.getElementById(id).value='');loadLogs();}
loadLogs();
</script>
</body>
</html>'''

logs.write_text(html, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + """

## v0.31.1 Logs page UI fix

- Fixed patch syntax issue caused by JavaScript template literals inside Python f-strings.
- Rewrites `/logs` with safer JavaScript and visible log counts.
""", encoding='utf-8')

print('v0.31.1 logs page UI fix applied successfully.')
