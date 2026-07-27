
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
