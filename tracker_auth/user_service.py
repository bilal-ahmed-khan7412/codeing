
from __future__ import annotations
import time
from datetime import datetime
from tracker_audit.audit_db import get_conn, init_db, rows_to_dicts
from tracker_auth.passwords import hash_password, verify_password, is_hashed


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _validate_password_length(password: str):
    if len(password) < 8 or len(password) > 12:
        raise ValueError('Password must be between 8 and 12 characters long.')


# Login rate-limiting policy. Single-process app (not horizontally
# scaled), so an in-memory tracker is sufficient - no Redis/DB table
# needed. Keyed by lowercased email so this doesn't depend on trusting
# a client-supplied IP header.
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 15 * 60
LOGIN_LOCKOUT_SECONDS = 15 * 60


class UserService:
    def __init__(self):
        init_db()
        self.ensure_super_admin()
        self.ensure_maintainer()
        self._failed_logins: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}

    def is_locked_out(self, email: str) -> bool:
        key = (email or '').strip().lower()
        until = self._locked_until.get(key)
        if until is None:
            return False
        if time.time() >= until:
            self._locked_until.pop(key, None)
            self._failed_logins.pop(key, None)
            return False
        return True

    def record_failed_attempt(self, email: str):
        key = (email or '').strip().lower()
        if not key:
            return
        cutoff = time.time() - LOGIN_ATTEMPT_WINDOW_SECONDS
        attempts = [t for t in self._failed_logins.get(key, []) if t >= cutoff]
        attempts.append(time.time())
        self._failed_logins[key] = attempts
        if len(attempts) >= LOGIN_ATTEMPT_LIMIT:
            self._locked_until[key] = time.time() + LOGIN_LOCKOUT_SECONDS

    def clear_attempts(self, email: str):
        key = (email or '').strip().lower()
        self._failed_logins.pop(key, None)
        self._locked_until.pop(key, None)

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
        if data.get('password'):
            _validate_password_length(data['password'])
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
        _validate_password_length(new_password)
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

    def get_user_by_id(self, user_id: int):
        conn = get_conn()
        row = conn.execute('SELECT id,name,email,department,role,status,created_at,last_login,last_logout,auto_cleanup_versions,llm_provider,llm_model FROM users WHERE id=?', (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_llm_credentials(self, user_id: int):
        conn = get_conn()
        row = conn.execute('SELECT llm_provider,llm_api_key_encrypted,llm_model,llm_base_url FROM users WHERE id=?', (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else {}

    def count_users(self) -> int:
        conn = get_conn()
        count = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
        conn.close()
        return count

    def get_user_by_email(self, email: str):
        conn = get_conn()
        row = conn.execute('SELECT * FROM users WHERE lower(email)=lower(?)', (email,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def ensure_super_admin(self):
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

    def ensure_maintainer(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM users WHERE lower(email)='maintainer@example.com'")
        count = cur.fetchone()['c']
        if count == 0:
            # Fixed application-maintainer account, seeded once. Tickets no
            # longer ask the creator to pick an assignee; an Admin-role
            # account is enough for full ticket visibility, this just gives
            # that a stable, dedicated identity instead of pointing at
            # whichever admin happened to be around.
            cur.execute('''INSERT INTO users(name,email,password,department,role,status,created_at)
                           VALUES(?,?,?,?,?,?,?)''', (
                'Maintainer', 'maintainer@example.com', hash_password('maintainer123'), 'Engineering', 'Admin', 'Active', now()
            ))
        conn.commit()
        conn.close()

    def signup(self, data: dict):
        """Signup with clear errors for duplicate/blank requests."""
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        department = (data.get('department') or '').strip()
        if not name or not email or not password:
            raise ValueError('Name, email, and password are required.')
        if '@' not in email:
            raise ValueError('Please enter a valid email address.')
        _validate_password_length(password)
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

    def approve_user(self, user_id: int, role: str):
        role = role if role in {'Admin', 'User'} else 'User'
        conn = get_conn()
        conn.execute('UPDATE users SET role=?, status=? WHERE id=?', (role, 'Active', user_id))
        conn.commit()
        conn.close()

    def reject_user(self, user_id: int):
        conn = get_conn()
        conn.execute('UPDATE users SET status=? WHERE id=?', ('Rejected', user_id))
        conn.commit()
        conn.close()

    def deactivate_user(self, user_id: int):
        conn = get_conn()
        conn.execute('UPDATE users SET status=? WHERE id=?', ('Inactive', user_id))
        conn.commit()
        conn.close()

    def update_role(self, user_id: int, role: str):
        if role not in {'Admin', 'User'}:
            raise ValueError('role must be Admin or User')
        conn = get_conn()
        conn.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))
        conn.commit()
        conn.close()

    def update_profile(self, current_email: str, data: dict):
        fields = []
        values = []
        if data.get('name'):
            fields.append('name=?'); values.append(data['name'].strip())
        if data.get('email'):
            fields.append('email=?'); values.append(data['email'].strip())
        if data.get('department'):
            fields.append('department=?'); values.append(data['department'].strip())
        if data.get('password'):
            _validate_password_length(data['password'])
            fields.append('password=?'); values.append(hash_password(data['password']))
        # Presence check, not truthiness - this is a boolean toggle, and a
        # truthy-only check would make it impossible to ever turn back off.
        if 'auto_cleanup_versions' in data:
            fields.append('auto_cleanup_versions=?'); values.append(1 if data['auto_cleanup_versions'] else 0)
        if 'llm_provider' in data:
            fields.append('llm_provider=?'); values.append((data['llm_provider'] or '').strip())
        if 'llm_model' in data:
            fields.append('llm_model=?'); values.append((data['llm_model'] or '').strip())
        if 'llm_base_url' in data:
            base_url = (data['llm_base_url'] or '').strip()
            if base_url and (data.get('llm_provider') or '').strip().lower() == 'custom':
                from tracker_llm.url_safety import is_public_http_url
                if not is_public_http_url(base_url):
                    raise ValueError('That base URL is not reachable as a public address.')
            fields.append('llm_base_url=?'); values.append(base_url)
        if data.get('llm_api_key'):
            # Non-empty = set a new key. A blank field on save leaves the
            # existing key untouched - clearing it is a separate explicit
            # action (llm_api_key_clear) so a plain "leave it blank" submit
            # can't accidentally wipe out an already-configured key.
            from tracker_auth.key_crypto import encrypt_api_key
            fields.append('llm_api_key_encrypted=?'); values.append(encrypt_api_key(data['llm_api_key']))
        if data.get('llm_api_key_clear'):
            fields.append('llm_api_key_encrypted=?'); values.append('')
        if not fields:
            return
        values.append(current_email)
        conn = get_conn()
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE lower(email)=lower(?)", values)
        conn.commit()
        conn.close()
