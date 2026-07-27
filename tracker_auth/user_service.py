
from __future__ import annotations
from datetime import datetime
from tracker_audit.audit_db import get_conn, init_db, rows_to_dicts
from tracker_auth.passwords import hash_password, verify_password, is_hashed


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class UserService:
    def __init__(self):
        init_db()

    def authenticate(self, email: str, password: str):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND status="Active"', (email,))
        row = cur.fetchone()
        if row and verify_password(password, row['password']):
            # Migrate old plain-text passwords to hashed storage after successful login.
            if not is_hashed(row['password']):
                cur.execute('UPDATE users SET password=? WHERE id=?', (hash_password(password), row['id']))
            cur.execute('UPDATE users SET last_login=? WHERE id=?', (now(), row['id']))
            conn.commit()
            cur.execute('SELECT * FROM users WHERE id=?', (row['id'],))
            row = cur.fetchone()
            conn.close()
            return dict(row)
        conn.close()
        return None

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
            hash_password(data.get('password','password123')),
            data.get('department','').strip(),
            data.get('role','Manager'),
            data.get('status','Active'),
            now()
        ))
        conn.commit()
        conn.close()


    def reset_password(self, user_id: int, new_password: str):
        if not new_password:
            raise ValueError('new_password is required')
        conn = get_conn()
        conn.execute('UPDATE users SET password=? WHERE id=?', (hash_password(new_password), user_id))
        conn.commit()
        conn.close()

    def update_user(self, user_id: int, data: dict):
        fields = ['name','email','department','role','status']
        values = [data.get(k,'') for k in fields]
        conn = get_conn()
        conn.execute('''UPDATE users SET name=?, email=?, department=?, role=?, status=? WHERE id=?''', values + [user_id])
        if data.get('password'):
            conn.execute('UPDATE users SET password=? WHERE id=?', (hash_password(data['password']), user_id))
        conn.commit()
        conn.close()


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
