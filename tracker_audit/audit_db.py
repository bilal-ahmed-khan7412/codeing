
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
    # CREATE TABLE IF NOT EXISTS above doesn't add columns to an
    # already-existing table, so migrate older DBs with a guarded ALTER.
    try:
        cur.execute("ALTER TABLE users ADD COLUMN auto_cleanup_versions INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    for col in ("llm_provider TEXT DEFAULT ''", "llm_api_key_encrypted TEXT DEFAULT ''", "llm_model TEXT DEFAULT ''", "llm_base_url TEXT DEFAULT ''"):
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
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
    try:
        cur.execute("ALTER TABLE task_tracker ADD COLUMN creator_notified INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        # Separate from `remarks` (set by the ticket's creator) - this is the
        # Maintainer's own optional response when resolving, so resolving a
        # ticket never overwrites whatever the creator originally wrote.
        cur.execute("ALTER TABLE task_tracker ADD COLUMN resolution_note TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        # Shared column, meaning depends on the ticket's category: for a
        # normal Issue ticket it's Bug/Error/Feature Request/Question; for
        # an API Key Request ticket it's which provider (Groq/Gemini/Other).
        # The two categories are mutually exclusive, so one column covers
        # both without ambiguity.
        cur.execute("ALTER TABLE task_tracker ADD COLUMN ticket_type TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
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
