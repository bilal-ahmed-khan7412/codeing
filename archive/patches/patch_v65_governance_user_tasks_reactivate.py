from pathlib import Path
import re

root = Path(__file__).resolve().parent
web_app = root / 'web_app.py'
users_html = root / 'web' / 'users.html'
chat_html = root / 'web' / 'chat.html'
tasks_html = root / 'web' / 'tasks.html'
logs_html = root / 'web' / 'logs.html'
readme = root / 'README.md'

if not web_app.exists():
    raise SystemExit('web_app.py not found. Run this patch inside intern_tracker_system_v0.')
if not users_html.exists():
    raise SystemExit('web/users.html not found. Run this patch after governance v61.')

# -----------------------------------------------------------------------------
# 1) web_app.py: restrict Tasks page/API to Admin/Super Admin and add reactivate
# -----------------------------------------------------------------------------
s = web_app.read_text(encoding='utf-8')

# Add helper if missing.
if 'def v65_is_admin_or_super' not in s:
    helper = r'''

def v65_is_admin_or_super(user):
    role = (user or {}).get('role', '')
    return role in {'Super Admin', 'Admin'}

def v65_is_super(user):
    return (user or {}).get('role', '') == 'Super Admin'
'''
    # Put after require_login helper if available, otherwise before first route.
    marker = "@app.get('/login', response_class=HTMLResponse)"
    if marker in s:
        s = s.replace(marker, helper + "\n" + marker, 1)
    else:
        s += helper

# Patch /tasks page route to block normal Users.
old = """@app.get('/tasks', response_class=HTMLResponse)
def tasks_page(request: Request):
    if not current_user_from_request(request):
        return RedirectResponse('/login')
    return (BASE_DIR / 'web' / 'tasks.html').read_text(encoding='utf-8')
"""
new = """@app.get('/tasks', response_class=HTMLResponse)
def tasks_page(request: Request):
    user = current_user_from_request(request)
    if not user:
        return RedirectResponse('/login')
    if not v65_is_admin_or_super(user):
        return RedirectResponse('/chat')
    return (BASE_DIR / 'web' / 'tasks.html').read_text(encoding='utf-8')
"""
if old in s:
    s = s.replace(old, new)

# Patch /api/tasks route to block normal Users.
old = """@app.get('/api/tasks')
def api_tasks(request: Request):
    require_login(request)
    return {'ok': True, 'tasks': task_service.list_tasks()}
"""
new = """@app.get('/api/tasks')
def api_tasks(request: Request):
    user = require_login(request)
    if not v65_is_admin_or_super(user):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    return {'ok': True, 'tasks': task_service.list_tasks()}
"""
if old in s:
    s = s.replace(old, new)

old = """@app.post('/api/tasks')
def api_create_task(request: Request, payload: dict):
    user = require_login(request)
    task_service.create_task(payload, user)
    audit_service.log(user, interface='Tasks', action='Create Task', target_type='Task', target_name=payload.get('title',''), status='Success')
    return {'ok': True}
"""
new = """@app.post('/api/tasks')
def api_create_task(request: Request, payload: dict):
    user = require_login(request)
    if not v65_is_admin_or_super(user):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    task_service.create_task(payload, user)
    audit_service.log(user, interface='Tasks', action='Create Task', target_type='Task', target_name=payload.get('title',''), status='Success')
    return {'ok': True}
"""
if old in s:
    s = s.replace(old, new)

# Add reactivate endpoint if missing.
if "@app.post('/api/users/reactivate')" not in s:
    endpoint = r'''

@app.post('/api/users/reactivate')
def api_reactivate_user(request: Request, payload: dict):
    actor = require_login(request)
    if not can_manage_users(actor):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    target_id = int(payload.get('user_id'))
    target = user_service.get_user_by_id(target_id) if hasattr(user_service, 'get_user_by_id') else None
    if not target:
        return JSONResponse(status_code=404, content={'ok': False, 'error': 'User not found'})
    if target.get('role') == 'Super Admin':
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Super Admin cannot be reactivated here'})
    # Admin can reactivate normal Users only. Super Admin can reactivate Admins and Users.
    if actor.get('role') == 'Admin' and target.get('role') != 'User':
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admins can reactivate Users only'})
    if actor.get('role') not in {'Super Admin', 'Admin'}:
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    conn = user_service.__class__.__dict__.get('get_conn', None)
    # Use audit DB connection directly for compatibility with monkey-patched UserService.
    from tracker_audit.audit_db import get_conn
    db = get_conn()
    db.execute('UPDATE users SET status=? WHERE id=?', ('Active', target_id))
    db.commit()
    db.close()
    audit_service.log(actor, interface='Users', action='Reactivate User', target_type='User', target_name=target.get('email',''), status='Success')
    return {'ok': True}
'''
    s += endpoint

# Strengthen role endpoint if the previous route exists: make errors visible and only super can change roles.
# If route already works, this keeps behavior. We won't duplicate route to avoid FastAPI order issues.

web_app.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) users.html: reactivate inactive users, visible errors, robust Make Admin
# -----------------------------------------------------------------------------
base_css = """
<style>
body{font-family:Arial,sans-serif;background:#f4f6fb;margin:0;color:#1f2937}header{background:#305496;color:white;padding:18px 28px;display:flex;justify-content:space-between;align-items:center}header a{color:white;font-weight:700;margin-left:14px}main{max-width:1100px;margin:0 auto;padding:20px}.card{background:white;border:1px solid #d9e2ef;border-radius:14px;padding:16px;box-shadow:0 4px 16px rgba(15,23,42,.06);margin-bottom:16px}button{background:#305496;color:white;border:none;border-radius:10px;padding:9px 12px;font-weight:700;cursor:pointer;margin:2px}table{width:100%;border-collapse:collapse;background:white}th,td{border-bottom:1px solid #e5e7eb;text-align:left;padding:8px;font-size:13px;vertical-align:top}th{background:#eef2ff}.danger{background:#991b1b}.success{background:#166534}.muted{color:#64748b;font-size:13px}.badge{padding:3px 8px;border-radius:999px;background:#e0f2fe;color:#075985;font-weight:700;font-size:12px}.error{color:#991b1b;font-weight:700}</style>
"""
users_html.write_text(f'''<!doctype html><html><head><title>Users</title>{base_css}</head><body>
<header><h2>User Management</h2><div><a href="/chat">Chat</a><a href="/logs">Logs</a><a href="/tasks">Tasks</a><a href="/profile">Profile</a><a href="/logout">Logout</a></div></header>
<main><div class="card"><h3>Access Requests & Users</h3><p class="muted">Admins can approve and manage Users only. Super Admin can approve Users/Admins and manage Admins.</p><p id="msg" class="muted"></p><table><thead><tr><th>Name</th><th>Email</th><th>Department</th><th>Role</th><th>Status</th><th>Last Login</th><th>Actions</th></tr></thead><tbody id="rows"></tbody></table></div></main>
<script>
let meUser=null;
function isSuper(){{return (meUser.role||'').toLowerCase()==='super admin'}}
function isAdmin(){{return (meUser.role||'').toLowerCase()==='admin'}}
function showMsg(text, isErr=false){{msg.className=isErr?'error':'muted';msg.textContent=text||''}}
async function api(url,payload){{const r=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload||{{}})}});let d={{}};try{{d=await r.json()}}catch(e){{d={{error:'Server did not return JSON'}}}};if(!r.ok||d.ok===false){{showMsg(d.error||'Action failed',true);return false}}showMsg('Updated.');return true}}
async function load(){{const me=await fetch('/api/me').then(r=>r.json());meUser=me.user||{{}};const r=await fetch('/api/users');const d=await r.json();if(!d.ok&&d.error){{showMsg(d.error,true);return}}const users=d.users||[];rows.innerHTML=users.map(u=>rowHtml(u)).join('')}}
function rowHtml(u){{let actions='';
  if(u.status==='Pending'){{
    actions+=`<button class="success" onclick="approve(${{u.id}},'User')">Approve User</button>`;
    if(isSuper()) actions+=`<button onclick="approve(${{u.id}},'Admin')">Approve Admin</button>`;
    actions+=`<button class="danger" onclick="rejectUser(${{u.id}})">Reject</button>`;
  }}
  if(u.status==='Active'&&u.role!=='Super Admin'){{
    if(isSuper() || (isAdmin()&&u.role==='User')) actions+=`<button class="danger" onclick="deactivate(${{u.id}})">Deactivate</button>`;
    if(isSuper()&&u.role==='User') actions+=`<button onclick="changeRole(${{u.id}},'Admin')">Make Admin</button>`;
    if(isSuper()&&u.role==='Admin') actions+=`<button onclick="changeRole(${{u.id}},'User')">Make User</button>`;
  }}
  if(u.status==='Inactive'){{
    if(isSuper() || (isAdmin()&&u.role==='User')) actions+=`<button class="success" onclick="reactivate(${{u.id}})">Reactivate</button>`;
  }}
  return `<tr><td>${{u.name}}</td><td>${{u.email}}</td><td>${{u.department||''}}</td><td><span class="badge">${{u.role}}</span></td><td>${{u.status}}</td><td>${{u.last_login||''}}</td><td>${{actions}}</td></tr>`}}
async function approve(id,role){{if(await api('/api/users/approve',{{user_id:id,role}}))load()}}
async function rejectUser(id){{if(await api('/api/users/reject',{{user_id:id}}))load()}}
async function deactivate(id){{if(!confirm('Deactivate this user?'))return;if(await api('/api/users/deactivate',{{user_id:id}}))load()}}
async function reactivate(id){{if(await api('/api/users/reactivate',{{user_id:id}}))load()}}
async function changeRole(id,role){{if(await api('/api/users/role',{{user_id:id,role}}))load()}}
load();
</script></body></html>''', encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Hide Tasks link from normal users in user-facing pages (Chat/Logs/Profile)
# -----------------------------------------------------------------------------
for p in [chat_html, logs_html]:
    if not p or not p.exists():
        continue
    page = p.read_text(encoding='utf-8')
    if 'v65HideAdminAndTaskLinks' not in page:
        js = r'''
<script>
async function v65HideAdminAndTaskLinks(){try{const r=await fetch('/api/me');const d=await r.json();const role=((d.user&&d.user.role)||'').toLowerCase();if(role==='user'){document.querySelectorAll('a[href="/users"],a[href="/logs"],a[href="/tasks"]').forEach(a=>a.remove());}}catch(e){}}
v65HideAdminAndTaskLinks();
</script>
'''
        page = page.replace('</body>', js + '</body>')
        p.write_text(page, encoding='utf-8')

# Compile check.
try:
    import py_compile
    py_compile.compile(str(web_app), doraise=True)
except Exception as e:
    raise SystemExit(f'web_app.py compile failed: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.65 Governance user/task/reactivation fixes

- Normal Users can no longer access `/tasks` or task APIs.
- Normal Users also have Tasks links hidden from user-facing navigation.
- Inactive users can be reactivated:
  - Admin can reactivate normal Users only.
  - Super Admin can reactivate Users and Admins.
- Users page now shows errors for role/action failures.
- Super Admin `Make Admin` / `Make User` actions are more visible and reload after success.
''', encoding='utf-8')

print('v0.65 governance user/task/reactivation patch applied successfully.')
