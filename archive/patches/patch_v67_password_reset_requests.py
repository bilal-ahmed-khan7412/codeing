from pathlib import Path

root = Path(__file__).resolve().parent
web_app = root / 'web_app.py'
web_dir = root / 'web'
readme = root / 'README.md'

if not web_app.exists():
    raise SystemExit('web_app.py not found. Run inside intern_tracker_system_v0 after governance patches.')
web_dir.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# v0.67 Forgot password request + temporary password reset workflow
# -----------------------------------------------------------------------------

s = web_app.read_text(encoding='utf-8')

# Add imports for sqlite/random if missing.
if 'import secrets' not in s:
    s = 'import secrets\nimport string\n' + s

# Add DB init and helper routes.
if 'v0.67 password reset request routes' not in s:
    routes = r"""

# v0.67 password reset request routes
from tracker_audit.audit_db import get_conn
try:
    from tracker_auth.passwords import hash_password
except Exception:
    import base64, hashlib, os
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        iterations = 260000
        dk = hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'), salt, iterations)
        return f'pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}'


def v67_init_password_reset_table():
    conn = get_conn()
    conn.execute('''
    CREATE TABLE IF NOT EXISTS password_reset_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        user_id INTEGER,
        status TEXT DEFAULT 'Pending',
        requested_at TEXT NOT NULL,
        processed_by TEXT DEFAULT '',
        processed_at TEXT DEFAULT '',
        remarks TEXT DEFAULT ''
    )
    ''')
    conn.commit()
    conn.close()


def v67_now():
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def v67_generate_temp_password():
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(8))
    return 'Temp@' + token


def v67_user_by_email(email: str):
    conn = get_conn()
    row = conn.execute('SELECT id,name,email,department,role,status FROM users WHERE lower(email)=lower(?)', (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


v67_init_password_reset_table()

@app.get('/forgot-password', response_class=HTMLResponse)
def forgot_password_page():
    return (BASE_DIR / 'web' / 'forgot_password.html').read_text(encoding='utf-8')

@app.post('/api/password-reset/request')
def api_password_reset_request(payload: dict):
    email = (payload.get('email') or '').strip().lower()
    remarks = (payload.get('remarks') or '').strip()
    if not email or '@' not in email:
        return JSONResponse(status_code=400, content={'ok': False, 'error': 'Valid email is required.'})
    target = v67_user_by_email(email)
    if not target:
        # Avoid leaking too much, but still log for admin visibility.
        audit_service.log({'name':'Unknown','email':email}, interface='Auth', action='Password Reset Request', target_type='User', target_name=email, status='Pending', summary='Password reset requested for email not currently active in users table')
        return {'ok': True, 'message': 'If this email exists, a reset request has been submitted.'}
    conn = get_conn()
    existing = conn.execute("SELECT id FROM password_reset_requests WHERE lower(email)=lower(?) AND status='Pending'", (email,)).fetchone()
    if existing:
        conn.close()
        return {'ok': True, 'message': 'A pending reset request already exists for this email.'}
    conn.execute('''INSERT INTO password_reset_requests(email,user_id,status,requested_at,remarks)
                    VALUES(?,?,?,?,?)''', (email, target.get('id'), 'Pending', v67_now(), remarks))
    conn.commit()
    conn.close()
    audit_service.log({'name':target.get('name',''), 'email':email}, interface='Auth', action='Password Reset Request', target_type='User', target_name=email, status='Pending', summary='User requested password reset')
    return {'ok': True, 'message': 'Password reset request submitted. Please wait for Admin/Super Admin approval.'}

@app.get('/api/password-reset/requests')
def api_password_reset_requests(request: Request):
    actor = require_login(request)
    if not v65_is_admin_or_super(actor):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    conn = get_conn()
    rows = conn.execute('''SELECT r.*, u.name, u.role, u.status AS user_status
                           FROM password_reset_requests r
                           LEFT JOIN users u ON u.id=r.user_id
                           ORDER BY r.id DESC LIMIT 200''').fetchall()
    conn.close()
    return {'ok': True, 'requests': [dict(x) for x in rows]}

@app.post('/api/password-reset/complete')
def api_password_reset_complete(request: Request, payload: dict):
    actor = require_login(request)
    if not v65_is_admin_or_super(actor):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    req_id = int(payload.get('request_id'))
    conn = get_conn()
    req = conn.execute('''SELECT r.*, u.role, u.email AS user_email, u.name AS user_name
                          FROM password_reset_requests r
                          LEFT JOIN users u ON u.id=r.user_id
                          WHERE r.id=?''', (req_id,)).fetchone()
    if not req:
        conn.close()
        return JSONResponse(status_code=404, content={'ok': False, 'error': 'Request not found'})
    req = dict(req)
    if req.get('status') != 'Pending':
        conn.close()
        return JSONResponse(status_code=400, content={'ok': False, 'error': 'Request is not pending'})
    target_role = req.get('role') or ''
    if actor.get('role') == 'Admin' and target_role != 'User':
        conn.close()
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admins can reset normal User passwords only'})
    if target_role == 'Super Admin':
        conn.close()
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Super Admin password must be changed from profile or handled directly by Super Admin'})
    temp_password = v67_generate_temp_password()
    conn.execute('UPDATE users SET password=? WHERE id=?', (hash_password(temp_password), req.get('user_id')))
    conn.execute('UPDATE password_reset_requests SET status=?, processed_by=?, processed_at=? WHERE id=?', ('Completed', actor.get('email',''), v67_now(), req_id))
    conn.commit()
    conn.close()
    audit_service.log(actor, interface='Users', action='Password Reset Completed', target_type='User', target_name=req.get('email',''), status='Success', summary='Temporary password generated. Password value not stored in logs.')
    # Return temp password once to admin/super admin so they can share via approved channel.
    return {'ok': True, 'temporary_password': temp_password, 'message': 'Temporary password generated. Share it with the user through an approved channel. User should change it after login.'}

@app.post('/api/password-reset/reject')
def api_password_reset_reject(request: Request, payload: dict):
    actor = require_login(request)
    if not v65_is_admin_or_super(actor):
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin or Super Admin only'})
    req_id = int(payload.get('request_id'))
    conn = get_conn()
    req = conn.execute('SELECT * FROM password_reset_requests WHERE id=?', (req_id,)).fetchone()
    if not req:
        conn.close()
        return JSONResponse(status_code=404, content={'ok': False, 'error': 'Request not found'})
    conn.execute('UPDATE password_reset_requests SET status=?, processed_by=?, processed_at=? WHERE id=?', ('Rejected', actor.get('email',''), v67_now(), req_id))
    conn.commit()
    conn.close()
    audit_service.log(actor, interface='Users', action='Password Reset Rejected', target_type='User', target_name=dict(req).get('email',''), status='Success')
    return {'ok': True}
"""
    s += routes

web_app.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# Pages: forgot password and users page enhancement for reset requests.
# -----------------------------------------------------------------------------
base_css = """
<style>
body{font-family:Arial,sans-serif;background:#f4f6fb;margin:0;color:#1f2937}header{background:#305496;color:white;padding:18px 28px;display:flex;justify-content:space-between;align-items:center}header a{color:white;font-weight:700;margin-left:14px}main{max-width:1100px;margin:0 auto;padding:20px}.card{background:white;border:1px solid #d9e2ef;border-radius:14px;padding:16px;box-shadow:0 4px 16px rgba(15,23,42,.06);margin-bottom:16px}input,textarea{padding:10px;border:1px solid #d9e2ef;border-radius:9px;font:inherit;width:100%;box-sizing:border-box}label{display:flex;flex-direction:column;gap:6px;font-weight:700;margin:8px 0}button{background:#305496;color:white;border:none;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}.muted{color:#64748b;font-size:13px}.error{color:#991b1b;font-weight:700}.success{color:#166534;font-weight:700}</style>
"""
(web_dir / 'forgot_password.html').write_text(f'''<!doctype html><html><head><title>Forgot Password</title>{base_css}</head><body>
<header><h2>Forgot Password</h2><div><a href="/login">Login</a></div></header>
<main><div class="card" style="max-width:520px;margin:40px auto;"><h2>Request password reset</h2><p class="muted">An Admin or Super Admin will review the request. If approved, they will provide a temporary password.</p><label>Email<input id="email"></label><label>Reason / message optional<textarea id="remarks"></textarea></label><button onclick="requestReset()">Submit Request</button><p id="msg" class="muted"></p></div></main>
<script>
async function requestReset(){{msg.textContent='Submitting...';const r=await fetch('/api/password-reset/request',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:email.value.trim(),remarks:remarks.value.trim()}})}});const d=await r.json();msg.className=d.ok?'success':'error';msg.textContent=d.message||d.error||'';}}
</script></body></html>''', encoding='utf-8')

# Add forgot password link to login.
login = web_dir / 'login.html'
if login.exists():
    h = login.read_text(encoding='utf-8')
    if '/forgot-password' not in h:
        h = h.replace('</button>', '</button><p class="muted"><a href="/forgot-password">Forgot password?</a></p>', 1)
    login.write_text(h, encoding='utf-8')

# Enhance users page: add reset request card/table using JS. If we rewrote users page earlier, append a card before </main>.
users = web_dir / 'users.html'
if users.exists():
    h = users.read_text(encoding='utf-8')
    if 'resetRows' not in h:
        card = r'''
<div class="card"><h3>Password Reset Requests</h3><p class="muted">Admins can reset normal Users only. Super Admin can reset Admins and Users. Temporary passwords are shown once.</p><p id="resetMsg" class="muted"></p><table><thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Status</th><th>Requested</th><th>Remarks</th><th>Actions</th></tr></thead><tbody id="resetRows"></tbody></table></div>
'''
        h = h.replace('</main>', card + '</main>')
        js = r'''
<script id="v67-reset-requests-js">
async function loadResetRequests(){
  const el=document.getElementById('resetRows'); if(!el)return;
  const r=await fetch('/api/password-reset/requests'); let d={}; try{d=await r.json()}catch(e){d={error:'Could not load reset requests'}};
  if(!d.ok){el.innerHTML=`<tr><td colspan="7">${d.error||'Not available'}</td></tr>`;return;}
  el.innerHTML=(d.requests||[]).map(x=>{let actions=''; if(x.status==='Pending'){actions+=`<button onclick="completeReset(${x.id})">Set Temporary Password</button><button class="danger" onclick="rejectReset(${x.id})">Reject</button>`;} return `<tr><td>${x.email}</td><td>${x.name||''}</td><td>${x.role||''}</td><td>${x.status}</td><td>${x.requested_at}</td><td>${x.remarks||''}</td><td>${actions}</td></tr>`}).join('');
}
async function completeReset(id){
  const r=await fetch('/api/password-reset/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:id})});
  const d=await r.json();
  const m=document.getElementById('resetMsg');
  if(d.ok){m.className='success';m.textContent='Temporary password: '+d.temporary_password+'  Share it with the user. This is shown once.';}else{m.className='error';m.textContent=d.error||'Reset failed';}
  loadResetRequests();
}
async function rejectReset(id){await fetch('/api/password-reset/reject',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:id})});loadResetRequests();}
loadResetRequests();
</script>
'''
        h = h.replace('</body>', js + '</body>')
    users.write_text(h, encoding='utf-8')

# Compile check.
try:
    import py_compile
    py_compile.compile(str(web_app), doraise=True)
except Exception as e:
    raise SystemExit(f'web_app.py compile failed: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.67 Password reset request workflow

- Added `/forgot-password` page.
- Users can request a password reset without logging in.
- Admin/Super Admin can review reset requests from `/users`.
- Admin can reset normal Users only.
- Super Admin can reset Admins and Users.
- System generates a temporary password and shows it once to the approver.
- Password values are not stored in logs.
''', encoding='utf-8')

print('v0.67 password reset request workflow patch applied successfully.')
