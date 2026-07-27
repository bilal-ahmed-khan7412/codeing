
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
