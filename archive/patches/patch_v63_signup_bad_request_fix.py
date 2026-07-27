from pathlib import Path

root = Path(__file__).resolve().parent
user_service = root / 'tracker_auth' / 'user_service.py'
web_app = root / 'web_app.py'
signup_html = root / 'web' / 'signup.html'
readme = root / 'README.md'

if not user_service.exists():
    raise SystemExit('tracker_auth/user_service.py not found. Run inside intern_tracker_system_v0 after governance patches.')
if not web_app.exists():
    raise SystemExit('web_app.py not found. Run inside intern_tracker_system_v0.')

# -----------------------------------------------------------------------------
# 1) Ensure hash_password exists in user_service.py even if v32 password patch was
#    not applied before the approval workflow patch.
# -----------------------------------------------------------------------------
s = user_service.read_text(encoding='utf-8')
if 'from tracker_auth.passwords import hash_password' not in s:
    import_line = "from tracker_audit.audit_db import get_conn, init_db, rows_to_dicts\n"
    if import_line in s:
        s = s.replace(import_line, import_line + "try:\n    from tracker_auth.passwords import hash_password\nexcept Exception:\n    import base64\n    import hashlib\n    import os\n    def hash_password(password: str) -> str:\n        salt = os.urandom(16)\n        iterations = 260000\n        dk = hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'), salt, iterations)\n        return f'pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}'\n")
    else:
        s = "try:\n    from tracker_auth.passwords import hash_password\nexcept Exception:\n    import base64\n    import hashlib\n    import os\n    def hash_password(password: str) -> str:\n        salt = os.urandom(16)\n        iterations = 260000\n        dk = hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'), salt, iterations)\n        return f'pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}'\n\n" + s

# Add duplicate-email friendly signup override.
if 'v0.63 signup bad request fix' not in s:
    s += r"""

# v0.63 signup bad request fix
# Gives clear errors for duplicate/blank signup requests and ensures hashing works.
def _v63_us_signup(self, data: dict):
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    department = (data.get('department') or '').strip()
    if not name or not email or not password:
        raise ValueError('Name, email, and password are required.')
    if '@' not in email:
        raise ValueError('Please enter a valid email address.')
    conn = get_conn()
    existing = conn.execute('SELECT email,status,role FROM users WHERE lower(email)=lower(?)', (email,)).fetchone()
    if existing:
        conn.close()
        status = existing['status'] if 'status' in existing.keys() else ''
        raise ValueError(f'An account request/user already exists for {email}. Current status: {status}.')
    conn.execute('''INSERT INTO users(name,email,password,department,role,status,created_at)
                    VALUES(?,?,?,?,?,?,?)''', (
        name, email, hash_password(password), department, 'User', 'Pending', now()
    ))
    conn.commit()
    conn.close()

UserService.signup = _v63_us_signup
"""

user_service.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) Improve /api/signup error response and log failed signup attempts.
# -----------------------------------------------------------------------------
s = web_app.read_text(encoding='utf-8')
old = """@app.post('/api/signup')\ndef api_signup(payload: dict):\n    try:\n        user_service.signup(payload)\n        audit_service.log({'name': payload.get('name',''), 'email': payload.get('email','')}, interface='Auth', action='Signup Request', target_type='User', target_name=payload.get('email',''), status='Pending', summary='User requested access')\n        return {'ok': True, 'message': 'Signup request submitted. Please wait for admin approval.'}\n    except Exception as e:\n        return JSONResponse(status_code=400, content={'ok': False, 'error': str(e)})\n"""
new = """@app.post('/api/signup')\ndef api_signup(payload: dict):\n    try:\n        user_service.signup(payload)\n        audit_service.log({'name': payload.get('name',''), 'email': payload.get('email','')}, interface='Auth', action='Signup Request', target_type='User', target_name=payload.get('email',''), status='Pending', summary='User requested access')\n        return {'ok': True, 'message': 'Signup request submitted. Please wait for admin approval.'}\n    except Exception as e:\n        err = str(e) or 'Signup failed.'\n        audit_service.log({'name': payload.get('name',''), 'email': payload.get('email','')}, interface='Auth', action='Signup Request Failed', target_type='User', target_name=payload.get('email',''), status='Failed', error_message=err)\n        return JSONResponse(status_code=400, content={'ok': False, 'error': err})\n"""
if old in s:
    s = s.replace(old, new)
else:
    print('Warning: exact /api/signup route not found. UserService fix still applied.')
web_app.write_text(s, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) Improve signup page client-side validation and visible errors.
# -----------------------------------------------------------------------------
if signup_html.exists():
    h = signup_html.read_text(encoding='utf-8')
    if 'v63 signup client fix' not in h:
        h = h.replace("async function signup(){const r=await fetch('/api/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name.value,email:email.value,password:password.value,department:department.value})});const d=await r.json();msg.textContent=d.message||d.error||'';if(d.ok) setTimeout(()=>location.href='/pending',800)}",
        "async function signup(){ /* v63 signup client fix */ msg.textContent='Submitting...'; const payload={name:name.value.trim(),email:email.value.trim(),password:password.value,department:department.value.trim()}; if(!payload.name||!payload.email||!payload.password){msg.textContent='Name, email, and password are required.'; return;} const r=await fetch('/api/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); let d={}; try{d=await r.json();}catch(e){d={error:'Signup failed. Server did not return JSON.'};} msg.textContent=d.message||d.error||'Signup failed.'; if(d.ok) setTimeout(()=>location.href='/pending',800)}")
        signup_html.write_text(h, encoding='utf-8')

# Compile checks.
try:
    import py_compile
    py_compile.compile(str(user_service), doraise=True)
    py_compile.compile(str(web_app), doraise=True)
except Exception as e:
    raise SystemExit(f'Compile check failed: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.63 Signup Bad Request Fix

- Fixed signup failures caused by missing `hash_password` import in some patch orders.
- Signup now returns clear errors for blank fields, invalid email, or duplicate email.
- Failed signup attempts are logged with the actual error message.
- Signup page now shows required-field validation and server error messages clearly.
''', encoding='utf-8')

print('v0.63 signup bad request fix applied successfully.')
