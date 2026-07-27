from pathlib import Path

root = Path(__file__).resolve().parent
web_app = root / 'web_app.py'
web_dir = root / 'web'
req = root / 'requirements.txt'
readme = root / 'README.md'

if not web_app.exists():
    raise SystemExit('web_app.py not found. Run this patch inside intern_tracker_system_v0.')
web_dir.mkdir(exist_ok=True)
(root / 'tracker_auth').mkdir(exist_ok=True)
(root / 'tracker_audit').mkdir(exist_ok=True)
(root / 'tracker_tasks').mkdir(exist_ok=True)
(root / 'data').mkdir(exist_ok=True)
(root / 'tracker_auth' / '__init__.py').write_text('', encoding='utf-8')
(root / 'tracker_audit' / '__init__.py').write_text('', encoding='utf-8')
(root / 'tracker_tasks' / '__init__.py').write_text('', encoding='utf-8')

# -----------------------------------------------------------------------------
# 1) Governance database and initial seed
# -----------------------------------------------------------------------------
(root / 'tracker_audit' / 'audit_db.py').write_text(r"""
from __future__ import annotations
from pathlib import Path
import sqlite3
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / 'data' / 'app.db'


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        department TEXT DEFAULT '',
        role TEXT DEFAULT 'Manager',
        status TEXT DEFAULT 'Active',
        created_at TEXT NOT NULL,
        last_login TEXT,
        last_logout TEXT
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        user_name TEXT,
        email TEXT,
        department TEXT,
        role TEXT,
        interface TEXT,
        action TEXT,
        target_type TEXT,
        target_name TEXT,
        input_workbook TEXT,
        output_workbook TEXT,
        status TEXT,
        approval_status TEXT,
        summary TEXT,
        error_message TEXT
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS task_tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        category TEXT DEFAULT 'General',
        priority TEXT DEFAULT 'Medium',
        status TEXT DEFAULT 'Pending',
        assigned_to TEXT DEFAULT '',
        created_by TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        due_date TEXT DEFAULT '',
        completed_at TEXT DEFAULT '',
        remarks TEXT DEFAULT ''
    )
    ''')
    cur.execute('SELECT COUNT(*) AS c FROM users')
    if cur.fetchone()['c'] == 0:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute('''INSERT INTO users(name,email,password,department,role,status,created_at)
                       VALUES(?,?,?,?,?,?,?)''',
                    ('Admin User','admin@example.com','admin123','Admin','Admin','Active',now))
    conn.commit()
    conn.close()


def rows_to_dicts(rows):
    return [dict(r) for r in rows]
""", encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) User service and permissions
# -----------------------------------------------------------------------------
(root / 'tracker_auth' / 'user_service.py').write_text(r"""
from __future__ import annotations
from datetime import datetime
from tracker_audit.audit_db import get_conn, init_db, rows_to_dicts


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class UserService:
    def __init__(self):
        init_db()

    def authenticate(self, email: str, password: str):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND password=? AND status="Active"', (email, password))
        row = cur.fetchone()
        if row:
            cur.execute('UPDATE users SET last_login=? WHERE id=?', (now(), row['id']))
            conn.commit()
            cur.execute('SELECT * FROM users WHERE id=?', (row['id'],))
            row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def logout(self, email: str):
        conn = get_conn()
        conn.execute('UPDATE users SET last_logout=? WHERE lower(email)=lower(?)', (now(), email))
        conn.commit()
        conn.close()

    def list_users(self):
        conn = get_conn()
        rows = conn.execute('SELECT id,name,email,department,role,status,created_at,last_login,last_logout FROM users ORDER BY id DESC').fetchall()
        conn.close()
        return rows_to_dicts(rows)

    def create_user(self, data: dict):
        conn = get_conn()
        conn.execute('''INSERT INTO users(name,email,password,department,role,status,created_at)
                        VALUES(?,?,?,?,?,?,?)''', (
            data.get('name','').strip(),
            data.get('email','').strip(),
            data.get('password','password123'),
            data.get('department','').strip(),
            data.get('role','Manager'),
            data.get('status','Active'),
            now()
        ))
        conn.commit()
        conn.close()

    def update_user(self, user_id: int, data: dict):
        fields = ['name','email','department','role','status']
        values = [data.get(k,'') for k in fields]
        conn = get_conn()
        conn.execute('''UPDATE users SET name=?, email=?, department=?, role=?, status=? WHERE id=?''', values + [user_id])
        if data.get('password'):
            conn.execute('UPDATE users SET password=? WHERE id=?', (data['password'], user_id))
        conn.commit()
        conn.close()
""", encoding='utf-8')

(root / 'tracker_auth' / 'permissions.py').write_text(r"""
MUTATING_COMMANDS = {
    'create_workbook','render_workbook','extend_intern','edit_task','update_task_status',
    'update_capstone','update_scenario','edit_project','update_project_status','add_intern',
    'add_intern_basic','add_intern_with_plan','add_holiday','create_plan','create_plan_from_draft',
    'edit_plan','edit_plan_week','apply_plan_to_intern'
}

ADMIN_ONLY_ROUTES = {'/users'}


def can_execute(user: dict | None, command: str) -> bool:
    if not user:
        return False
    role = user.get('role')
    if role == 'Admin':
        return True
    if role == 'Manager':
        return command not in {'create_workbook'} or True
    if role == 'Viewer':
        return command == 'summary'
    return False


def can_manage_users(user: dict | None) -> bool:
    return bool(user and user.get('role') == 'Admin')


def can_view_logs(user: dict | None) -> bool:
    return bool(user and user.get('role') in {'Admin','Manager','Viewer'})
""", encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Audit service
# -----------------------------------------------------------------------------
(root / 'tracker_audit' / 'audit_service.py').write_text(r"""
from __future__ import annotations
from datetime import datetime
import csv
from pathlib import Path
from tracker_audit.audit_db import get_conn, init_db, rows_to_dicts, BASE_DIR


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class AuditService:
    def __init__(self):
        init_db()

    def log(self, user=None, interface='', action='', target_type='', target_name='', input_workbook='', output_workbook='', status='Success', approval_status='', summary='', error_message=''):
        user = user or {}
        conn = get_conn()
        conn.execute('''INSERT INTO activity_logs(timestamp,user_name,email,department,role,interface,action,target_type,target_name,input_workbook,output_workbook,status,approval_status,summary,error_message)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            now(), user.get('name','Anonymous'), user.get('email',''), user.get('department',''), user.get('role',''),
            interface, action, target_type, target_name, input_workbook, output_workbook, status, approval_status, summary, error_message
        ))
        conn.commit()
        conn.close()

    def list_logs(self, limit=500, filters=None):
        filters = filters or {}
        sql = 'SELECT * FROM activity_logs WHERE 1=1'
        params = []
        for field in ['email','action','status','interface']:
            if filters.get(field):
                sql += f' AND {field} LIKE ?'
                params.append('%' + filters[field] + '%')
        if filters.get('q'):
            sql += ' AND (target_name LIKE ? OR summary LIKE ? OR input_workbook LIKE ? OR output_workbook LIKE ?)'
            q = '%' + filters['q'] + '%'
            params.extend([q,q,q,q])
        sql += ' ORDER BY id DESC LIMIT ?'
        params.append(limit)
        conn = get_conn()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return rows_to_dicts(rows)

    def export_csv(self):
        logs = self.list_logs(limit=10000)
        out = BASE_DIR / 'outputs' / 'activity_logs.csv'
        out.parent.mkdir(exist_ok=True)
        if not logs:
            out.write_text('No logs\n', encoding='utf-8')
            return str(out)
        with out.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(logs[0].keys()))
            writer.writeheader()
            writer.writerows(logs)
        return str(out)
""", encoding='utf-8')

# -----------------------------------------------------------------------------
# 4) Task tracker service
# -----------------------------------------------------------------------------
(root / 'tracker_tasks' / 'task_service.py').write_text(r"""
from __future__ import annotations
from datetime import datetime
from tracker_audit.audit_db import get_conn, init_db, rows_to_dicts


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class TaskService:
    def __init__(self):
        init_db()

    def list_tasks(self):
        conn = get_conn()
        rows = conn.execute('SELECT * FROM task_tracker ORDER BY id DESC').fetchall()
        conn.close()
        return rows_to_dicts(rows)

    def create_task(self, data, user=None):
        user = user or {}
        conn = get_conn()
        conn.execute('''INSERT INTO task_tracker(title,description,category,priority,status,assigned_to,created_by,created_at,due_date,remarks)
                        VALUES(?,?,?,?,?,?,?,?,?,?)''', (
            data.get('title','').strip(), data.get('description',''), data.get('category','General'), data.get('priority','Medium'),
            data.get('status','Pending'), data.get('assigned_to',''), user.get('name',''), now(), data.get('due_date',''), data.get('remarks','')
        ))
        conn.commit()
        conn.close()

    def update_task(self, task_id, data):
        conn = get_conn()
        completed_at = now() if data.get('status') == 'Completed' else data.get('completed_at','')
        conn.execute('''UPDATE task_tracker SET title=?,description=?,category=?,priority=?,status=?,assigned_to=?,due_date=?,completed_at=?,remarks=? WHERE id=?''', (
            data.get('title',''), data.get('description',''), data.get('category','General'), data.get('priority','Medium'),
            data.get('status','Pending'), data.get('assigned_to',''), data.get('due_date',''), completed_at, data.get('remarks',''), task_id
        ))
        conn.commit()
        conn.close()
""", encoding='utf-8')

# -----------------------------------------------------------------------------
# 5) Patch web_app.py with auth, users, logs, tasks, and audit wrappers
# -----------------------------------------------------------------------------
s = web_app.read_text(encoding='utf-8')

imports = """
from fastapi import Request
from fastapi.responses import RedirectResponse
from tracker_auth.user_service import UserService
from tracker_auth.permissions import can_execute, can_manage_users, can_view_logs
from tracker_audit.audit_service import AuditService
from tracker_tasks.task_service import TaskService
from tracker_audit.audit_db import init_db
"""
if 'from tracker_auth.user_service import UserService' not in s:
    s = s.replace('from fastapi.responses import HTMLResponse, FileResponse, JSONResponse', 'from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse')
    s = s.replace('from fastapi import FastAPI, UploadFile, File, Form, HTTPException', 'from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request')
    s = s.replace('from tracker_commands.validator import CommandValidationError', 'from tracker_commands.validator import CommandValidationError\nfrom tracker_auth.user_service import UserService\nfrom tracker_auth.permissions import can_execute, can_manage_users, can_view_logs\nfrom tracker_audit.audit_service import AuditService\nfrom tracker_tasks.task_service import TaskService\nfrom tracker_audit.audit_db import init_db')

if 'user_service = UserService()' not in s:
    s = s.replace('chat_service = ChatService()\n', 'chat_service = ChatService()\ninit_db()\nuser_service = UserService()\naudit_service = AuditService()\ntask_service = TaskService()\n')

# Add simple cookie-based helpers and routes before home route.
if 'def current_user_from_request' not in s:
    helpers = r'''

def current_user_from_request(request: Request):
    email = request.cookies.get('user_email')
    if not email:
        return None
    users = user_service.list_users()
    for u in users:
        if u.get('email','').lower() == email.lower() and u.get('status') == 'Active':
            return u
    return None


def require_login(request: Request):
    user = current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail='Login required')
    return user

@app.get('/login', response_class=HTMLResponse)
def login_page():
    return (BASE_DIR / 'web' / 'login.html').read_text(encoding='utf-8')

@app.post('/api/login')
def api_login(payload: dict):
    user = user_service.authenticate(payload.get('email',''), payload.get('password',''))
    if not user:
        return JSONResponse(status_code=401, content={'ok': False, 'error': 'Invalid login or inactive user'})
    audit_service.log(user, interface='Auth', action='Login', status='Success', summary='User logged in')
    res = JSONResponse({'ok': True, 'user': user})
    res.set_cookie('user_email', user['email'], httponly=False, samesite='lax')
    return res

@app.get('/logout')
def logout(request: Request):
    user = current_user_from_request(request)
    if user:
        user_service.logout(user['email'])
        audit_service.log(user, interface='Auth', action='Logout', status='Success', summary='User logged out')
    res = RedirectResponse('/login')
    res.delete_cookie('user_email')
    return res

@app.get('/api/me')
def api_me(request: Request):
    user = current_user_from_request(request)
    return {'ok': bool(user), 'user': user}

@app.get('/users', response_class=HTMLResponse)
def users_page(request: Request):
    user = current_user_from_request(request)
    if not can_manage_users(user):
        return RedirectResponse('/login')
    return (BASE_DIR / 'web' / 'users.html').read_text(encoding='utf-8')

@app.get('/logs', response_class=HTMLResponse)
def logs_page(request: Request):
    user = current_user_from_request(request)
    if not can_view_logs(user):
        return RedirectResponse('/login')
    return (BASE_DIR / 'web' / 'logs.html').read_text(encoding='utf-8')

@app.get('/tasks', response_class=HTMLResponse)
def tasks_page(request: Request):
    if not current_user_from_request(request):
        return RedirectResponse('/login')
    return (BASE_DIR / 'web' / 'tasks.html').read_text(encoding='utf-8')

@app.get('/api/users')
def api_users(request: Request):
    user = require_login(request)
    if not can_manage_users(user):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin only'})
    return {'ok': True, 'users': user_service.list_users()}

@app.post('/api/users')
def api_create_user(request: Request, payload: dict):
    user = require_login(request)
    if not can_manage_users(user):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin only'})
    user_service.create_user(payload)
    audit_service.log(user, interface='Users', action='Create User', target_type='User', target_name=payload.get('email',''), status='Success')
    return {'ok': True}

@app.get('/api/logs')
def api_logs(request: Request, q: str = '', email: str = '', action: str = '', status: str = '', interface: str = ''):
    user = require_login(request)
    if not can_view_logs(user):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Not allowed'})
    filters = {'q': q, 'email': email, 'action': action, 'status': status, 'interface': interface}
    logs = audit_service.list_logs(filters=filters)
    if user.get('role') != 'Admin':
        logs = [x for x in logs if x.get('email') == user.get('email')]
    return {'ok': True, 'logs': logs}

@app.get('/api/logs/export')
def api_logs_export(request: Request):
    user = require_login(request)
    if not can_view_logs(user):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Not allowed'})
    path = audit_service.export_csv()
    audit_service.log(user, interface='Logs', action='Export Logs', status='Success', output_workbook=Path(path).name)
    return FileResponse(path, filename=Path(path).name)

@app.get('/api/tasks')
def api_tasks(request: Request):
    require_login(request)
    return {'ok': True, 'tasks': task_service.list_tasks()}

@app.post('/api/tasks')
def api_create_task(request: Request, payload: dict):
    user = require_login(request)
    task_service.create_task(payload, user)
    audit_service.log(user, interface='Tasks', action='Create Task', target_type='Task', target_name=payload.get('title',''), status='Success')
    return {'ok': True}
'''
    s = s.replace('@app.get("/", response_class=HTMLResponse)', helpers + '\n@app.get("/", response_class=HTMLResponse)')

# Patch execute_command to include request, permission check, and audit logs.
s = s.replace('@app.post("/api/execute")\ndef execute_command(payload: dict):', '@app.post("/api/execute")\ndef execute_command(request: Request, payload: dict):')
if 'audit_service.log(user, interface=\'Forms\'' not in s:
    old = """def execute_command(request: Request, payload: dict):\n    try:\n        cmd = payload.get(\"command\")\n        args = payload.get(\"args\") or {}\n"""
    new = """def execute_command(request: Request, payload: dict):\n    user = require_login(request)\n    try:\n        cmd = payload.get(\"command\")\n        if not can_execute(user, cmd):\n            audit_service.log(user, interface='Forms', action=cmd or 'Unknown', status='Blocked', summary='Permission denied')\n            return JSONResponse(status_code=403, content={'ok': False, 'error': 'Permission denied'})\n        args = payload.get(\"args\") or {}\n"""
    s = s.replace(old, new)
    old_success = """        return response\n    except CommandValidationError as e:\n        return JSONResponse(status_code=400, content={\"ok\": False, \"error\": str(e)})\n    except Exception as e:\n        return JSONResponse(status_code=500, content={\"ok\": False, \"error\": str(e)})\n"""
    new_success = """        audit_service.log(user, interface='Forms', action=cmd, target_name=args.get('intern') or args.get('name') or args.get('plan_name') or '', input_workbook=args.get('source') or args.get('workbook') or '', output_workbook=Path(result.output_path).name if result.output_path else '', status='Success' if result.ok else 'Failed', summary=result.message)\n        return response\n    except CommandValidationError as e:\n        audit_service.log(user, interface='Forms', action=payload.get('command',''), status='Failed', error_message=str(e))\n        return JSONResponse(status_code=400, content={\"ok\": False, \"error\": str(e)})\n    except Exception as e:\n        audit_service.log(user, interface='Forms', action=payload.get('command',''), status='Failed', error_message=str(e))\n        return JSONResponse(status_code=500, content={\"ok\": False, \"error\": str(e)})\n"""
    s = s.replace(old_success, new_success)

# Patch upload_workbook route to accept request and log.
s = s.replace('@app.post("/api/upload")\ndef upload_workbook(file: UploadFile = File(...)):', '@app.post("/api/upload")\ndef upload_workbook(request: Request, file: UploadFile = File(...)):')
if "action='Upload Workbook'" not in s:
    s = s.replace("    with dst.open(\"wb\") as f:\n        shutil.copyfileobj(file.file, f)\n    return {\"ok\": True, \"filename\": filename, \"path\": str(dst)}", "    with dst.open(\"wb\") as f:\n        shutil.copyfileobj(file.file, f)\n    user = current_user_from_request(request)\n    audit_service.log(user, interface='Forms', action='Upload Workbook', target_type='Workbook', target_name=filename, output_workbook=filename, status='Success')\n    return {\"ok\": True, \"filename\": filename, \"path\": str(dst)}")

# Patch chat approve to log approved and result (if route exists).
if "interface='Chat'" not in s and "def chat_approve" in s:
    s = s.replace("def chat_approve(payload: dict):", "def chat_approve(request: Request, payload: dict):")
    s = s.replace("    draft_id = payload.get('draft_id')", "    user = require_login(request)\n    draft_id = payload.get('draft_id')")
    s = s.replace("        result = chat_service.approve(draft_id)\n        if result.get('output_path'):", "        audit_service.log(user, interface='Chat', action=getattr(draft, 'command', 'chat_approve'), approval_status='Approved', status='Started', summary='Chat proposal approved')\n        result = chat_service.approve(draft_id)\n        audit_service.log(user, interface='Chat', action=getattr(draft, 'command', 'chat_approve'), target_name=(getattr(draft, 'args', {}) or {}).get('intern') or (getattr(draft, 'args', {}) or {}).get('name') or (getattr(draft, 'args', {}) or {}).get('plan_name') or '', input_workbook=(getattr(draft, 'args', {}) or {}).get('source') or (getattr(draft, 'args', {}) or {}).get('workbook') or '', output_workbook=Path(result.get('output_path','')).name if result.get('output_path') else '', approval_status='Approved', status='Success' if result.get('ok') else 'Failed', summary=result.get('message',''), error_message=result.get('error',''))\n        if result.get('output_path'):")

web_app.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 6) Frontend pages
# -----------------------------------------------------------------------------
base_css = """
<style>
body{font-family:Arial,sans-serif;background:#f4f6fb;margin:0;color:#1f2937}header{background:#305496;color:white;padding:18px 28px;display:flex;justify-content:space-between}header a{color:white;font-weight:700;margin-left:14px}main{max-width:1100px;margin:0 auto;padding:20px}.card{background:white;border:1px solid #d9e2ef;border-radius:14px;padding:16px;box-shadow:0 4px 16px rgba(15,23,42,.06);margin-bottom:16px}input,select,textarea{padding:10px;border:1px solid #d9e2ef;border-radius:9px;font:inherit;width:100%;box-sizing:border-box}label{display:flex;flex-direction:column;gap:6px;font-weight:700;margin:8px 0}button{background:#305496;color:white;border:none;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}table{width:100%;border-collapse:collapse;background:white}th,td{border-bottom:1px solid #e5e7eb;text-align:left;padding:9px;font-size:14px;vertical-align:top}th{background:#eef2ff}.grid{display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:12px}.danger{background:#991b1b}.muted{color:#64748b;font-size:13px}.nav a{color:white}</style>
"""

(web_dir / 'login.html').write_text(f'''<!doctype html><html><head><title>Login</title>{base_css}</head><body>
<header><h2>Intern Tracker Login</h2></header><main><div class="card" style="max-width:430px;margin:40px auto;">
<h2>Sign in</h2><p class="muted">Default admin: admin@example.com / admin123</p>
<label>Email<input id="email" value="admin@example.com"></label><label>Password<input id="password" type="password" value="admin123"></label>
<button onclick="login()">Login</button><p id="msg" class="muted"></p></div></main>
<script>
async function login(){{const r=await fetch('/api/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:email.value,password:password.value}})}});const d=await r.json();if(d.ok) location.href='/'; else msg.textContent=d.error||'Login failed';}}
</script></body></html>''', encoding='utf-8')

(web_dir / 'users.html').write_text(f'''<!doctype html><html><head><title>Users</title>{base_css}</head><body>
<header><h2>User Management</h2><div class="nav"><a href="/">Forms</a><a href="/chat">Chat</a><a href="/logs">Logs</a><a href="/tasks">Tasks</a><a href="/logout">Logout</a></div></header>
<main><div class="card"><h3>Add User</h3><div class="grid"><label>Name<input id="name"></label><label>Email<input id="email"></label><label>Password<input id="password" value="password123"></label><label>Department<input id="department"></label><label>Role<select id="role"><option>Admin</option><option selected>Manager</option><option>Viewer</option></select></label><label>Status<select id="status"><option selected>Active</option><option>Inactive</option></select></label></div><button onclick="addUser()">Add User</button></div><div class="card"><h3>Users</h3><table><thead><tr><th>Name</th><th>Email</th><th>Department</th><th>Role</th><th>Status</th><th>Last Login</th><th>Last Logout</th></tr></thead><tbody id="rows"></tbody></table></div></main>
<script>
async function load(){{const r=await fetch('/api/users');const d=await r.json();rows.innerHTML=(d.users||[]).map(u=>`<tr><td>${{u.name}}</td><td>${{u.email}}</td><td>${{u.department||''}}</td><td>${{u.role}}</td><td>${{u.status}}</td><td>${{u.last_login||''}}</td><td>${{u.last_logout||''}}</td></tr>`).join('')}}
async function addUser(){{await fetch('/api/users',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:name.value,email:email.value,password:password.value,department:department.value,role:role.value,status:status.value}})}});load()}}load();
</script></body></html>''', encoding='utf-8')

(web_dir / 'logs.html').write_text(f'''<!doctype html><html><head><title>Activity Logs</title>{base_css}</head><body>
<header><h2>Activity Logs</h2><div class="nav"><a href="/">Forms</a><a href="/chat">Chat</a><a href="/users">Users</a><a href="/tasks">Tasks</a><a href="/logout">Logout</a></div></header>
<main><div class="card"><h3>Filters</h3><div class="grid"><label>Search<input id="q"></label><label>Email<input id="email"></label><label>Action<input id="action"></label><label>Status<input id="status"></label></div><button onclick="load()">Apply</button> <a href="/api/logs/export"><button>Export CSV</button></a></div><div class="card"><table><thead><tr><th>Time</th><th>User</th><th>Role</th><th>Interface</th><th>Action</th><th>Target</th><th>Status</th><th>Approval</th><th>Output</th><th>Summary</th></tr></thead><tbody id="rows"></tbody></table></div></main>
<script>
async function load(){{const url=`/api/logs?q=${{encodeURIComponent(q.value)}}&email=${{encodeURIComponent(email.value)}}&action=${{encodeURIComponent(action.value)}}&status=${{encodeURIComponent(status.value)}}`;const r=await fetch(url);const d=await r.json();rows.innerHTML=(d.logs||[]).map(x=>`<tr><td>${{x.timestamp}}</td><td>${{x.user_name}}</td><td>${{x.role}}</td><td>${{x.interface}}</td><td>${{x.action}}</td><td>${{x.target_name||''}}</td><td>${{x.status}}</td><td>${{x.approval_status||''}}</td><td>${{x.output_workbook||''}}</td><td>${{x.summary||x.error_message||''}}</td></tr>`).join('')}}load();
</script></body></html>''', encoding='utf-8')

(web_dir / 'tasks.html').write_text(f'''<!doctype html><html><head><title>Task Tracker</title>{base_css}</head><body>
<header><h2>Task Tracker</h2><div class="nav"><a href="/">Forms</a><a href="/chat">Chat</a><a href="/logs">Logs</a><a href="/users">Users</a><a href="/logout">Logout</a></div></header>
<main><div class="card"><h3>Create Task</h3><div class="grid"><label>Title<input id="title"></label><label>Assigned To<input id="assigned_to"></label><label>Category<select id="category"><option>Frontend</option><option>Backend</option><option>LLM</option><option>Workbook</option><option>Governance</option><option>Bug</option><option>Deployment</option></select></label><label>Priority<select id="priority"><option>Low</option><option selected>Medium</option><option>High</option></select></label><label>Status<select id="status"><option>Pending</option><option>In Progress</option><option>Blocked</option><option>Completed</option><option>Cancelled</option></select></label><label>Due Date<input id="due_date"></label></div><label>Description<textarea id="description"></textarea></label><label>Remarks<textarea id="remarks"></textarea></label><button onclick="addTask()">Add Task</button></div><div class="card"><h3>Tasks</h3><table><thead><tr><th>ID</th><th>Title</th><th>Category</th><th>Priority</th><th>Status</th><th>Assigned</th><th>Created By</th><th>Due</th><th>Remarks</th></tr></thead><tbody id="rows"></tbody></table></div></main>
<script>
async function load(){{const r=await fetch('/api/tasks');const d=await r.json();rows.innerHTML=(d.tasks||[]).map(t=>`<tr><td>${{t.id}}</td><td>${{t.title}}</td><td>${{t.category}}</td><td>${{t.priority}}</td><td>${{t.status}}</td><td>${{t.assigned_to}}</td><td>${{t.created_by}}</td><td>${{t.due_date}}</td><td>${{t.remarks}}</td></tr>`).join('')}}
async function addTask(){{await fetch('/api/tasks',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{title:title.value,description:description.value,category:category.value,priority:priority.value,status:status.value,assigned_to:assigned_to.value,due_date:due_date.value,remarks:remarks.value}})}});load()}}load();
</script></body></html>''', encoding='utf-8')

# -----------------------------------------------------------------------------
# 7) Add nav links to existing pages if simple header exists.
# -----------------------------------------------------------------------------
for page in ['index.html','chat.html']:
    p = web_dir / page
    if p.exists():
        txt = p.read_text(encoding='utf-8')
        if '/logs' not in txt and '</header>' in txt:
            txt = txt.replace('</header>', '<div style="padding:0 28px 12px;background:#305496;"><a style="color:white;font-weight:700;margin-right:14px;" href="/users">Users</a><a style="color:white;font-weight:700;margin-right:14px;" href="/logs">Logs</a><a style="color:white;font-weight:700;margin-right:14px;" href="/tasks">Tasks</a><a style="color:white;font-weight:700;" href="/logout">Logout</a></div></header>')
            p.write_text(txt, encoding='utf-8')

# README
if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.30 Governance + Task Tracker Add-on

Added basic governance features:

- Login/logout
- User management page: `/users`
- Activity logs page: `/logs`
- Task tracker page: `/tasks`
- SQLite database: `data/app.db`
- Tables: `users`, `activity_logs`, `task_tracker`
- Default admin: `admin@example.com` / `admin123`
- Logs user actions including login/logout, workbook uploads, form commands, chat approvals, task creation, and log exports.

Containerization remains a later deployment step.
''', encoding='utf-8')

print('v0.30 governance + task tracker add-on applied successfully.')
