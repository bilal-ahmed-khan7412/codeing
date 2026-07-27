from pathlib import Path

root = Path(__file__).resolve().parent
user_service = root / 'tracker_auth' / 'user_service.py'
permissions = root / 'tracker_auth' / 'permissions.py'
web_app = root / 'web_app.py'
web_dir = root / 'web'
readme = root / 'README.md'

for p in [user_service, permissions, web_app]:
    if not p.exists():
        raise SystemExit(f'{p} not found. Apply governance add-on first, then run this patch inside intern_tracker_system_v0.')
web_dir.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# 1) Permissions: Super Admin/Admin/User model
# -----------------------------------------------------------------------------
permissions.write_text(r'''
MUTATING_COMMANDS = {
    'create_workbook','render_workbook','extend_intern','extend_intern_with_plan','edit_task','update_task_status',
    'update_capstone','update_scenario','edit_project','update_project_status','add_intern',
    'add_intern_basic','add_intern_with_plan','add_holiday','create_plan','create_plan_from_draft',
    'edit_plan','edit_plan_week','apply_plan_to_intern'
}


def role_name(user: dict | None) -> str:
    if not user:
        return ''
    return (user.get('role') or '').strip()


def is_super_admin(user: dict | None) -> bool:
    return role_name(user).lower() == 'super admin'


def is_admin(user: dict | None) -> bool:
    return role_name(user).lower() == 'admin'


def is_user(user: dict | None) -> bool:
    return role_name(user).lower() == 'user'


def can_execute(user: dict | None, command: str) -> bool:
    if not user or user.get('status') != 'Active':
        return False
    # Normal users can use the tracker application normally.
    if is_super_admin(user) or is_admin(user) or is_user(user):
        return True
    # Legacy roles from earlier builds stay supported.
    if role_name(user) in {'Manager'}:
        return True
    if role_name(user) in {'Viewer'}:
        return command == 'summary'
    return False


def can_manage_users(user: dict | None) -> bool:
    return bool(user and user.get('status') == 'Active' and (is_super_admin(user) or is_admin(user)))


def can_view_logs(user: dict | None) -> bool:
    return bool(user and user.get('status') == 'Active' and (is_super_admin(user) or is_admin(user)))


def can_manage_admins(user: dict | None) -> bool:
    return is_super_admin(user)


def can_assign_role(actor: dict | None, role: str) -> bool:
    role = (role or '').strip()
    if is_super_admin(actor):
        return role in {'Admin', 'User'}
    if is_admin(actor):
        return role == 'User'
    return False


def can_modify_target(actor: dict | None, target: dict | None) -> bool:
    if not actor or not target:
        return False
    target_role = role_name(target)
    if is_super_admin(actor):
        # Super Admin can manage admins and users, but should not deactivate itself through simple UI.
        return target_role in {'Admin', 'User'}
    if is_admin(actor):
        return target_role == 'User'
    return False
''', encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) UserService: signup, approval, super admin seed, profile update
# -----------------------------------------------------------------------------
s = user_service.read_text(encoding='utf-8')
if 'v0.61 approval-role user service extensions' not in s:
    s += r"""

# v0.61 approval-role user service extensions
# Adds Super Admin/Admin/User approval workflow while preserving older methods.

def _v61_us_get_user_by_id(self, user_id: int):
    conn = get_conn()
    row = conn.execute('SELECT id,name,email,department,role,status,created_at,last_login,last_logout FROM users WHERE id=?', (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _v61_us_get_user_by_email(self, email: str):
    conn = get_conn()
    row = conn.execute('SELECT * FROM users WHERE lower(email)=lower(?)', (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _v61_us_ensure_super_admin(self):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users WHERE role='Super Admin'")
    count = cur.fetchone()['c']
    if count == 0:
        # Temporary bootstrap account. Super Admin should change this after first login.
        cur.execute('''INSERT INTO users(name,email,password,department,role,status,created_at)
                       VALUES(?,?,?,?,?,?,?)''', (
            'Super Admin', 'superadmin@example.com', hash_password('superadmin123'), 'Management', 'Super Admin', 'Active', now()
        ))
    conn.commit()
    conn.close()


def _v61_us_signup(self, data: dict):
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    department = (data.get('department') or '').strip()
    if not name or not email or not password:
        raise ValueError('name, email, and password are required')
    conn = get_conn()
    conn.execute('''INSERT INTO users(name,email,password,department,role,status,created_at)
                    VALUES(?,?,?,?,?,?,?)''', (
        name, email, hash_password(password), department, 'User', 'Pending', now()
    ))
    conn.commit()
    conn.close()


def _v61_us_approve(self, user_id: int, role: str):
    role = role if role in {'Admin', 'User'} else 'User'
    conn = get_conn()
    conn.execute('UPDATE users SET role=?, status=? WHERE id=?', (role, 'Active', user_id))
    conn.commit()
    conn.close()


def _v61_us_reject(self, user_id: int):
    conn = get_conn()
    conn.execute('UPDATE users SET status=? WHERE id=?', ('Rejected', user_id))
    conn.commit()
    conn.close()


def _v61_us_deactivate(self, user_id: int):
    conn = get_conn()
    conn.execute('UPDATE users SET status=? WHERE id=?', ('Inactive', user_id))
    conn.commit()
    conn.close()


def _v61_us_update_role(self, user_id: int, role: str):
    if role not in {'Admin', 'User'}:
        raise ValueError('role must be Admin or User')
    conn = get_conn()
    conn.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))
    conn.commit()
    conn.close()


def _v61_us_update_profile(self, current_email: str, data: dict):
    fields = []
    values = []
    if data.get('name'):
        fields.append('name=?'); values.append(data['name'].strip())
    if data.get('email'):
        fields.append('email=?'); values.append(data['email'].strip())
    if data.get('department'):
        fields.append('department=?'); values.append(data['department'].strip())
    if data.get('password'):
        fields.append('password=?'); values.append(hash_password(data['password']))
    if not fields:
        return
    values.append(current_email)
    conn = get_conn()
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE lower(email)=lower(?)", values)
    conn.commit()
    conn.close()

# Attach methods.
UserService.get_user_by_id = _v61_us_get_user_by_id
UserService.get_user_by_email = _v61_us_get_user_by_email
UserService.ensure_super_admin = _v61_us_ensure_super_admin
UserService.signup = _v61_us_signup
UserService.approve_user = _v61_us_approve
UserService.reject_user = _v61_us_reject
UserService.deactivate_user = _v61_us_deactivate
UserService.update_role = _v61_us_update_role
UserService.update_profile = _v61_us_update_profile

# Wrap __init__ to ensure one bootstrap Super Admin exists.
if not hasattr(UserService, '_base_init_v61'):
    UserService._base_init_v61 = UserService.__init__
    def _v61_init(self, *args, **kwargs):
        UserService._base_init_v61(self, *args, **kwargs)
        self.ensure_super_admin()
    UserService.__init__ = _v61_init
"""
user_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) web_app: routes for signup, profile, approvals, role changes
# -----------------------------------------------------------------------------
s = web_app.read_text(encoding='utf-8')

# Imports: add can_assign_role/can_modify_target/can_manage_admins if not present.
s = s.replace(
    'from tracker_auth.permissions import can_execute, can_manage_users, can_view_logs',
    'from tracker_auth.permissions import can_execute, can_manage_users, can_view_logs, can_assign_role, can_modify_target, can_manage_admins'
)

if 'v0.61 approval-role governance routes' not in s:
    routes = r'''

# v0.61 approval-role governance routes
@app.get('/signup', response_class=HTMLResponse)
def signup_page():
    return (BASE_DIR / 'web' / 'signup.html').read_text(encoding='utf-8')

@app.get('/pending', response_class=HTMLResponse)
def pending_page():
    return (BASE_DIR / 'web' / 'pending.html').read_text(encoding='utf-8')

@app.get('/profile', response_class=HTMLResponse)
def profile_page(request: Request):
    if not current_user_from_request(request):
        return RedirectResponse('/login')
    return (BASE_DIR / 'web' / 'profile.html').read_text(encoding='utf-8')

@app.post('/api/signup')
def api_signup(payload: dict):
    try:
        user_service.signup(payload)
        audit_service.log({'name': payload.get('name',''), 'email': payload.get('email','')}, interface='Auth', action='Signup Request', target_type='User', target_name=payload.get('email',''), status='Pending', summary='User requested access')
        return {'ok': True, 'message': 'Signup request submitted. Please wait for admin approval.'}
    except Exception as e:
        return JSONResponse(status_code=400, content={'ok': False, 'error': str(e)})

@app.post('/api/users/approve')
def api_approve_user(request: Request, payload: dict):
    actor = require_login(request)
    if not can_manage_users(actor):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    target_id = int(payload.get('user_id'))
    role = payload.get('role') or 'User'
    target = user_service.get_user_by_id(target_id)
    if not target:
        return JSONResponse(status_code=404, content={'ok': False, 'error': 'User not found'})
    if not can_assign_role(actor, role):
        audit_service.log(actor, interface='Users', action='Approve User', target_type='User', target_name=target.get('email',''), status='Blocked', summary=f'Role assignment blocked: {role}')
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'You cannot approve this role'})
    user_service.approve_user(target_id, role)
    audit_service.log(actor, interface='Users', action='Approve User', target_type='User', target_name=target.get('email',''), status='Success', summary=f'Approved as {role}')
    return {'ok': True}

@app.post('/api/users/reject')
def api_reject_user(request: Request, payload: dict):
    actor = require_login(request)
    if not can_manage_users(actor):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    target_id = int(payload.get('user_id'))
    target = user_service.get_user_by_id(target_id)
    if not target:
        return JSONResponse(status_code=404, content={'ok': False, 'error': 'User not found'})
    if target.get('role') in {'Admin', 'Super Admin'} and not can_manage_admins(actor):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Only Super Admin can reject/admin-manage admins'})
    user_service.reject_user(target_id)
    audit_service.log(actor, interface='Users', action='Reject User', target_type='User', target_name=target.get('email',''), status='Success')
    return {'ok': True}

@app.post('/api/users/deactivate')
def api_deactivate_user(request: Request, payload: dict):
    actor = require_login(request)
    if not can_manage_users(actor):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    target_id = int(payload.get('user_id'))
    target = user_service.get_user_by_id(target_id)
    if not target:
        return JSONResponse(status_code=404, content={'ok': False, 'error': 'User not found'})
    if target.get('role') == 'Super Admin':
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Super Admin cannot be deactivated here'})
    if not can_modify_target(actor, target):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Only Super Admin can manage Admins'})
    user_service.deactivate_user(target_id)
    audit_service.log(actor, interface='Users', action='Deactivate User', target_type='User', target_name=target.get('email',''), status='Success')
    return {'ok': True}

@app.post('/api/users/role')
def api_change_user_role(request: Request, payload: dict):
    actor = require_login(request)
    if not can_manage_admins(actor):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Only Super Admin can change Admin/User roles'})
    target_id = int(payload.get('user_id'))
    role = payload.get('role') or 'User'
    target = user_service.get_user_by_id(target_id)
    if not target:
        return JSONResponse(status_code=404, content={'ok': False, 'error': 'User not found'})
    if target.get('role') == 'Super Admin':
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Cannot change Super Admin role'})
    user_service.update_role(target_id, role)
    audit_service.log(actor, interface='Users', action='Change Role', target_type='User', target_name=target.get('email',''), status='Success', summary=f'Role changed to {role}')
    return {'ok': True}

@app.post('/api/profile')
def api_update_profile(request: Request, payload: dict):
    actor = require_login(request)
    old_email = actor.get('email')
    user_service.update_profile(old_email, payload)
    new_email = payload.get('email') or old_email
    audit_service.log(actor, interface='Profile', action='Update Profile', status='Success', summary='User updated own profile')
    res = JSONResponse({'ok': True})
    if new_email != old_email:
        res.set_cookie('user_email', new_email, httponly=False, samesite='lax')
    return res
'''
    # Add routes before file listing or at end.
    s += routes

web_app.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 4) Pages: signup, pending, profile, improved users page
# -----------------------------------------------------------------------------
base_css = """
<style>
body{font-family:Arial,sans-serif;background:#f4f6fb;margin:0;color:#1f2937}header{background:#305496;color:white;padding:18px 28px;display:flex;justify-content:space-between;align-items:center}header a{color:white;font-weight:700;margin-left:14px}main{max-width:1100px;margin:0 auto;padding:20px}.card{background:white;border:1px solid #d9e2ef;border-radius:14px;padding:16px;box-shadow:0 4px 16px rgba(15,23,42,.06);margin-bottom:16px}input,select,textarea{padding:10px;border:1px solid #d9e2ef;border-radius:9px;font:inherit;width:100%;box-sizing:border-box}label{display:flex;flex-direction:column;gap:6px;font-weight:700;margin:8px 0}button{background:#305496;color:white;border:none;border-radius:10px;padding:9px 12px;font-weight:700;cursor:pointer;margin:2px}table{width:100%;border-collapse:collapse;background:white}th,td{border-bottom:1px solid #e5e7eb;text-align:left;padding:8px;font-size:13px;vertical-align:top}th{background:#eef2ff}.grid{display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:12px}.danger{background:#991b1b}.success{background:#166534}.muted{color:#64748b;font-size:13px}.badge{padding:3px 8px;border-radius:999px;background:#e0f2fe;color:#075985;font-weight:700;font-size:12px}</style>
"""

(web_dir / 'signup.html').write_text(f'''<!doctype html><html><head><title>Signup</title>{base_css}</head><body>
<header><h2>Request Access</h2><div><a href="/login">Login</a></div></header>
<main><div class="card" style="max-width:520px;margin:40px auto;"><h2>Create access request</h2><p class="muted">Your account will be pending until an Admin or Super Admin approves it.</p>
<label>Name<input id="name"></label><label>Email<input id="email"></label><label>Password<input id="password" type="password"></label><label>Department<input id="department"></label>
<button onclick="signup()">Submit Request</button><p id="msg" class="muted"></p></div></main>
<script>
async function signup(){{const r=await fetch('/api/signup',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:name.value,email:email.value,password:password.value,department:department.value}})}});const d=await r.json();msg.textContent=d.message||d.error||'';if(d.ok) setTimeout(()=>location.href='/pending',800)}}
</script></body></html>''', encoding='utf-8')

(web_dir / 'pending.html').write_text(f'''<!doctype html><html><head><title>Pending Approval</title>{base_css}</head><body>
<header><h2>Pending Approval</h2><div><a href="/login">Login</a></div></header><main><div class="card" style="max-width:560px;margin:40px auto;"><h2>Your request is pending</h2><p>Your access request has been submitted. Please wait for an Admin or Super Admin to approve your account.</p></div></main></body></html>''', encoding='utf-8')

(web_dir / 'profile.html').write_text(f'''<!doctype html><html><head><title>Profile</title>{base_css}</head><body>
<header><h2>Profile</h2><div><a href="/chat">Chat</a><a href="/logout">Logout</a></div></header>
<main><div class="card" style="max-width:560px;"><h3>Update profile</h3><p class="muted">Super Admin should change the temporary bootstrap email/password after first login.</p><label>Name<input id="name"></label><label>Email<input id="email"></label><label>Department<input id="department"></label><label>New Password<input id="password" type="password"></label><button onclick="save()">Save</button><p id="msg"></p></div></main>
<script>
async function me(){{const r=await fetch('/api/me');const d=await r.json();if(d.user){{name.value=d.user.name||'';email.value=d.user.email||'';department.value=d.user.department||'';}}}};
async function save(){{const r=await fetch('/api/profile',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:name.value,email:email.value,department:department.value,password:password.value}})}});const d=await r.json();msg.textContent=d.ok?'Saved.':(d.error||'Error');}}me();
</script></body></html>''', encoding='utf-8')

(web_dir / 'users.html').write_text(f'''<!doctype html><html><head><title>Users</title>{base_css}</head><body>
<header><h2>User Management</h2><div><a href="/chat">Chat</a><a href="/logs">Logs</a><a href="/tasks">Tasks</a><a href="/profile">Profile</a><a href="/logout">Logout</a></div></header>
<main><div class="card"><h3>Access Requests & Users</h3><p class="muted">Admins can approve users as User only. Super Admin can approve as User or Admin and manage Admins.</p><table><thead><tr><th>Name</th><th>Email</th><th>Department</th><th>Role</th><th>Status</th><th>Last Login</th><th>Actions</th></tr></thead><tbody id="rows"></tbody></table></div></main>
<script>
let meUser=null;
async function load(){{const me=await fetch('/api/me').then(r=>r.json());meUser=me.user||{{}};const r=await fetch('/api/users');const d=await r.json();const users=d.users||[];rows.innerHTML=users.map(u=>rowHtml(u)).join('')}}
function isSuper(){{return (meUser.role||'').toLowerCase()==='super admin'}}
function isAdmin(){{return (meUser.role||'').toLowerCase()==='admin'}}
function rowHtml(u){{let actions='';if(u.status==='Pending'){{actions+=`<button class="success" onclick="approve(${{u.id}},'User')">Approve User</button>`;if(isSuper())actions+=`<button onclick="approve(${{u.id}},'Admin')">Approve Admin</button>`;actions+=`<button class="danger" onclick="reject(${{u.id}})">Reject</button>`;}}if(u.status==='Active'&&u.role!=='Super Admin'){{if(isSuper() || (isAdmin()&&u.role==='User')) actions+=`<button class="danger" onclick="deactivate(${{u.id}})">Deactivate</button>`;if(isSuper()&&u.role==='User') actions+=`<button onclick="role(${{u.id}},'Admin')">Make Admin</button>`;if(isSuper()&&u.role==='Admin') actions+=`<button onclick="role(${{u.id}},'User')">Make User</button>`;}}return `<tr><td>${{u.name}}</td><td>${{u.email}}</td><td>${{u.department||''}}</td><td><span class="badge">${{u.role}}</span></td><td>${{u.status}}</td><td>${{u.last_login||''}}</td><td>${{actions}}</td></tr>`}}
async function approve(id,role){{await fetch('/api/users/approve',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id:id,role}})}});load()}}
async function reject(id){{await fetch('/api/users/reject',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id:id}})}});load()}}
async function deactivate(id){{if(!confirm('Deactivate this user?'))return;await fetch('/api/users/deactivate',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id:id}})}});load()}}
async function role(id,role){{await fetch('/api/users/role',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id:id,role}})}});load()}}
load();
</script></body></html>''', encoding='utf-8')

# Add signup link to login page if it exists.
login = web_dir / 'login.html'
if login.exists():
    s = login.read_text(encoding='utf-8')
    if '/signup' not in s:
        s = s.replace('</button><p id="msg"', '</button><p class="muted"><a href="/signup">Request access</a></p><p id="msg"')
    login.write_text(s, encoding='utf-8')

# Hide Users/Logs links for normal User on chat/tasks via small JS helper.
for page in ['chat.html','tasks.html']:
    p = web_dir / page
    if not p.exists():
        continue
    s = p.read_text(encoding='utf-8')
    if 'v61HideAdminLinks' not in s:
        js = r'''
<script>
async function v61HideAdminLinks(){try{const r=await fetch('/api/me');const d=await r.json();const role=(d.user&&d.user.role)||'';if(role.toLowerCase()==='user'){document.querySelectorAll('a[href="/users"],a[href="/logs"]').forEach(a=>a.remove());}}catch(e){}}
v61HideAdminLinks();
</script>
'''
        s = s.replace('</body>', js + '</body>')
        p.write_text(s, encoding='utf-8')

# Compile checks.
try:
    import py_compile
    py_compile.compile(str(user_service), doraise=True)
    py_compile.compile(str(permissions), doraise=True)
    py_compile.compile(str(web_app), doraise=True)
except Exception as e:
    raise SystemExit(f'Compile check failed: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.61 Super Admin / Admin / User approval workflow

- Roles are now: Super Admin, Admin, User.
- A single bootstrap Super Admin is seeded if none exists:
  - email: `superadmin@example.com`
  - password: `superadmin123`
- Super Admin should change email/password from `/profile` after first login.
- New users submit requests through `/signup` and start as `Pending`.
- Admins can approve pending users as `User` only.
- Super Admin can approve as `User` or `Admin`, promote/demote admins, and manage all users/admins.
- Normal Users can use the app but cannot access Users or Logs.
''', encoding='utf-8')

print('v0.61 Super Admin/Admin/User approval workflow patch applied successfully.')
