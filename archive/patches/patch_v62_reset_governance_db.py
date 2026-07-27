from pathlib import Path
import sqlite3
from datetime import datetime

root = Path(__file__).resolve().parent
db_path = root / 'data' / 'app.db'
readme = root / 'README.md'

if not db_path.exists():
    raise SystemExit(f'Database not found: {db_path}. Start the app once or apply governance add-on first.')

try:
    from tracker_auth.passwords import hash_password
except Exception:
    import hashlib, os, base64
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        iterations = 260000
        dk = hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'), salt, iterations)
        return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"

SUPER_EMAIL = 'superadmin@example.com'
SUPER_PASSWORD = 'superadmin123'
SUPER_NAME = 'Super Admin'
SUPER_DEPT = 'Management'

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Ensure tables exist even if DB is partially initialized.
cur.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    department TEXT DEFAULT '',
    role TEXT DEFAULT 'User',
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

# Clean governance state only.
cur.execute('DELETE FROM users')
cur.execute('DELETE FROM activity_logs')
cur.execute('DELETE FROM task_tracker')

# Reset SQLite autoincrement counters for a clean demo.
cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('users','activity_logs','task_tracker')")

now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
cur.execute('''INSERT INTO users(name,email,password,department,role,status,created_at,last_login,last_logout)
               VALUES(?,?,?,?,?,?,?,?,?)''', (
    SUPER_NAME,
    SUPER_EMAIL,
    hash_password(SUPER_PASSWORD),
    SUPER_DEPT,
    'Super Admin',
    'Active',
    now,
    None,
    None
))

conn.commit()
conn.close()

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.62 Reset governance database for clean demo

- Cleans `users`, `activity_logs`, and `task_tracker` tables from `data/app.db`.
- Re-seeds only one Super Admin:
  - Email: `superadmin@example.com`
  - Password: `superadmin123`
- Logs and pending signup requests are removed for a clean governance demo.
''', encoding='utf-8')

print('v0.62 governance database reset completed successfully.')
print('Super Admin email:', SUPER_EMAIL)
print('Super Admin temporary password:', SUPER_PASSWORD)
print('Next: restart the app and login at /login, then change credentials at /profile.')
