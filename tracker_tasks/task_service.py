
from __future__ import annotations
from datetime import datetime
from tracker_audit.audit_db import get_conn, init_db, rows_to_dicts


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class TaskService:
    def __init__(self):
        init_db()

    def list_tasks(self, assigned_to=None):
        conn = get_conn()
        if assigned_to:
            rows = conn.execute('SELECT * FROM task_tracker WHERE assigned_to=? ORDER BY id DESC', (assigned_to,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM task_tracker ORDER BY id DESC').fetchall()
        conn.close()
        return rows_to_dicts(rows)

    def get_task(self, task_id):
        conn = get_conn()
        rows = conn.execute('SELECT * FROM task_tracker WHERE id=?', (task_id,)).fetchall()
        conn.close()
        result = rows_to_dicts(rows)
        return result[0] if result else None

    def create_task(self, data, user=None):
        user = user or {}
        conn = get_conn()
        conn.execute('''INSERT INTO task_tracker(title,description,category,priority,status,assigned_to,created_by,created_at,due_date,remarks)
                        VALUES(?,?,?,?,?,?,?,?,?,?)''', (
            data.get('title','').strip(), data.get('description','')[:200], data.get('category','General'), data.get('priority','Medium'),
            data.get('status','Pending'), data.get('assigned_to',''), user.get('name',''), now(), data.get('due_date',''), data.get('remarks','')
        ))
        conn.commit()
        conn.close()

    def update_task(self, task_id, data):
        conn = get_conn()
        completed_at = now() if data.get('status') == 'Completed' else data.get('completed_at','')
        conn.execute('''UPDATE task_tracker SET title=?,description=?,category=?,priority=?,status=?,assigned_to=?,due_date=?,completed_at=?,remarks=?,creator_notified=?,resolution_note=? WHERE id=?''', (
            data.get('title',''), data.get('description','')[:200], data.get('category','General'), data.get('priority','Medium'),
            data.get('status','Pending'), data.get('assigned_to',''), data.get('due_date',''), completed_at, data.get('remarks',''), data.get('creator_notified', 0), data.get('resolution_note',''), task_id
        ))
        conn.commit()
        conn.close()

    def list_unnotified_resolved(self, created_by):
        conn = get_conn()
        rows = conn.execute("SELECT * FROM task_tracker WHERE created_by=? AND status='Completed' AND creator_notified=0 ORDER BY id DESC", (created_by,)).fetchall()
        conn.close()
        return rows_to_dicts(rows)

    def mark_notified(self, created_by):
        conn = get_conn()
        conn.execute("UPDATE task_tracker SET creator_notified=1 WHERE created_by=? AND status='Completed' AND creator_notified=0", (created_by,))
        conn.commit()
        conn.close()

    def mark_notified_one(self, task_id):
        conn = get_conn()
        conn.execute("UPDATE task_tracker SET creator_notified=1 WHERE id=?", (task_id,))
        conn.commit()
        conn.close()
