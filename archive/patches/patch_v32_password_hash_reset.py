from pathlib import Path

root = Path(__file__).resolve().parent
user_service_path = root / 'tracker_auth' / 'user_service.py'
web_app_path = root / 'web_app.py'
users_html_path = root / 'web' / 'users.html'
readme_path = root / 'README.md'

for p in [user_service_path, web_app_path, users_html_path]:
    if not p.exists():
        raise SystemExit(f'{p} not found. Apply governance add-on first, then run this patch inside intern_tracker_system_v0.')

# -----------------------------------------------------------------------------
# 1) Add password hashing helper using Python stdlib only.
# -----------------------------------------------------------------------------
(root / 'tracker_auth' / 'passwords.py').write_text(r'''
from __future__ import annotations
import base64
import hashlib
import hmac
import os

PREFIX = 'pbkdf2_sha256'
ITERATIONS = 260000


def hash_password(password: str) -> str:
    """Return a salted PBKDF2-SHA256 password hash.

    Format: pbkdf2_sha256$iterations$salt$hash
    Uses only Python standard library, so no extra dependency is required.
    """
    password = password or ''
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return f"{PREFIX}${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def is_hashed(value: str) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX + '$')


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against hashed or legacy plain-text storage.

    Legacy plain-text support is included only for migration. When a plain-text
    password matches, caller should re-save it as a hash.
    """
    password = password or ''
    stored = stored or ''
    if not is_hashed(stored):
        return hmac.compare_digest(password, stored)
    try:
        _prefix, iterations, salt_b64, hash_b64 = stored.split('$', 3)
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(hash_b64.encode())
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iterations))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False
''', encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Patch UserService: hash new/reset passwords and migrate legacy passwords.
# -----------------------------------------------------------------------------
s = user_service_path.read_text(encoding='utf-8')
if 'from tracker_auth.passwords import hash_password, verify_password, is_hashed' not in s:
    s = s.replace('from tracker_audit.audit_db import get_conn, init_db, rows_to_dicts', 'from tracker_audit.audit_db import get_conn, init_db, rows_to_dicts\nfrom tracker_auth.passwords import hash_password, verify_password, is_hashed')

old_auth = """    def authenticate(self, email: str, password: str):\n        conn = get_conn()\n        cur = conn.cursor()\n        cur.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND password=? AND status=\"Active\"', (email, password))\n        row = cur.fetchone()\n        if row:\n            cur.execute('UPDATE users SET last_login=? WHERE id=?', (now(), row['id']))\n            conn.commit()\n            cur.execute('SELECT * FROM users WHERE id=?', (row['id'],))\n            row = cur.fetchone()\n        conn.close()\n        return dict(row) if row else None\n"""
new_auth = """    def authenticate(self, email: str, password: str):\n        conn = get_conn()\n        cur = conn.cursor()\n        cur.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND status=\"Active\"', (email,))\n        row = cur.fetchone()\n        if row and verify_password(password, row['password']):\n            # Migrate old plain-text passwords to hashed storage after successful login.\n            if not is_hashed(row['password']):\n                cur.execute('UPDATE users SET password=? WHERE id=?', (hash_password(password), row['id']))\n            cur.execute('UPDATE users SET last_login=? WHERE id=?', (now(), row['id']))\n            conn.commit()\n            cur.execute('SELECT * FROM users WHERE id=?', (row['id'],))\n            row = cur.fetchone()\n            conn.close()\n            return dict(row)\n        conn.close()\n        return None\n"""
if old_auth in s:
    s = s.replace(old_auth, new_auth)

# create_user hashes password
old_create = """            data.get('password','password123'),\n"""
if old_create in s:
    s = s.replace(old_create, "            hash_password(data.get('password','password123')),\n")

# update_user hashes changed password
old_update_pass = """        if data.get('password'):\n            conn.execute('UPDATE users SET password=? WHERE id=?', (data['password'], user_id))\n"""
new_update_pass = """        if data.get('password'):\n            conn.execute('UPDATE users SET password=? WHERE id=?', (hash_password(data['password']), user_id))\n"""
if old_update_pass in s:
    s = s.replace(old_update_pass, new_update_pass)

# Add reset_password method
if 'def reset_password' not in s:
    insert = r'''
    def reset_password(self, user_id: int, new_password: str):
        if not new_password:
            raise ValueError('new_password is required')
        conn = get_conn()
        conn.execute('UPDATE users SET password=? WHERE id=?', (hash_password(new_password), user_id))
        conn.commit()
        conn.close()

'''
    marker = '    def update_user(self, user_id: int, data: dict):'
    if marker not in s:
        raise SystemExit('Could not find update_user method in user_service.py')
    s = s.replace(marker, insert + marker)

user_service_path.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Patch web_app.py: admin-only reset password endpoint + login failure log.
# -----------------------------------------------------------------------------
s = web_app_path.read_text(encoding='utf-8')

# Add failed login attempt log if not present
old_login_fail = """    if not user:\n        return JSONResponse(status_code=401, content={'ok': False, 'error': 'Invalid login or inactive user'})\n"""
new_login_fail = """    if not user:\n        audit_service.log({'name':'Unknown','email':payload.get('email','')}, interface='Auth', action='Login Failed', status='Failed', summary='Invalid login or inactive user')\n        return JSONResponse(status_code=401, content={'ok': False, 'error': 'Invalid login or inactive user'})\n"""
if old_login_fail in s and 'Login Failed' not in s:
    s = s.replace(old_login_fail, new_login_fail)

# Add reset endpoint after create user endpoint.
if "@app.post('/api/users/reset-password')" not in s:
    marker = """@app.post('/api/users')\ndef api_create_user(request: Request, payload: dict):\n    user = require_login(request)\n    if not can_manage_users(user):\n        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin only'})\n    user_service.create_user(payload)\n    audit_service.log(user, interface='Users', action='Create User', target_type='User', target_name=payload.get('email',''), status='Success')\n    return {'ok': True}\n"""
    addition = marker + r'''

@app.post('/api/users/reset-password')
def api_reset_password(request: Request, payload: dict):
    user = require_login(request)
    if not can_manage_users(user):
        audit_service.log(user, interface='Users', action='Reset Password', status='Blocked', summary='Admin only')
        return JSONResponse(status_code=403, content={'ok': False, 'error': 'Admin only'})
    target_id = int(payload.get('user_id'))
    new_password = payload.get('new_password', '')
    user_service.reset_password(target_id, new_password)
    audit_service.log(user, interface='Users', action='Reset Password', target_type='User', target_name=str(target_id), status='Success', summary='Admin reset user password')
    return {'ok': True}
'''
    if marker not in s:
        raise SystemExit('Could not find api_create_user route in web_app.py')
    s = s.replace(marker, addition)

web_app_path.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 4) Patch users.html: add reset password button for admin page.
# -----------------------------------------------------------------------------
s = users_html_path.read_text(encoding='utf-8')

# Add action column and Reset button in rows rendering.
s = s.replace('<th>Last Logout</th></tr>', '<th>Last Logout</th><th>Actions</th></tr>')
old_rows = """<td>${u.last_logout||''}</td></tr>"""
new_rows = """<td>${u.last_logout||''}</td><td><button onclick=\"resetPassword(${u.id}, '${u.email}')\">Reset Password</button></td></tr>"""
if old_rows in s and 'resetPassword' not in s:
    s = s.replace(old_rows, new_rows)

# If the exact row template differs, do a broader inject.
if 'function resetPassword' not in s:
    s = s.replace('</script></body></html>', r'''
async function resetPassword(userId, email){
  const newPass = prompt('Enter new password for ' + email + ':');
  if(!newPass) return;
  const r = await fetch('/api/users/reset-password', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({user_id:userId,new_password:newPass})
  });
  const d = await r.json();
  if(d.ok) alert('Password reset successfully.');
  else alert(d.error || 'Password reset failed.');
}
</script></body></html>''')

users_html_path.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 5) README note.
# -----------------------------------------------------------------------------
if readme_path.exists():
    readme_path.write_text(readme_path.read_text(encoding='utf-8') + r'''

## v0.32 Password hashing and admin password reset

- New passwords are stored using PBKDF2-SHA256 salted hashes in `users.password`.
- Existing plain-text passwords are migrated to hashes after the user's next successful login.
- Failed login attempts are logged.
- Admin-only password reset endpoint added: `/api/users/reset-password`.
- User Management page now includes a Reset Password action.
''', encoding='utf-8')

print('v0.32 password hashing + admin reset patch applied successfully.')
