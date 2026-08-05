
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

    def count_actions(self, actions: list[str], status: str = 'Success') -> int:
        if not actions:
            return 0
        placeholders = ','.join('?' for _ in actions)
        sql = f'SELECT COUNT(*) AS c FROM activity_logs WHERE action IN ({placeholders}) AND status=?'
        conn = get_conn()
        count = conn.execute(sql, [*actions, status]).fetchone()['c']
        conn.close()
        return count

    def top_targets(self, actions: list[str], status: str = 'Success', limit: int = 5) -> list[dict]:
        if not actions:
            return []
        placeholders = ','.join('?' for _ in actions)
        sql = f"""SELECT target_name, COUNT(*) AS c FROM activity_logs
                  WHERE action IN ({placeholders}) AND status=? AND target_name != ''
                  GROUP BY target_name ORDER BY c DESC LIMIT ?"""
        conn = get_conn()
        rows = conn.execute(sql, [*actions, status, limit]).fetchall()
        conn.close()
        return [{'name': r['target_name'], 'count': r['c']} for r in rows]

    def hours_saved(self, minutes_by_action: dict[str, float], status: str = 'Success') -> float:
        """Rough estimate: sum(count of successful actions of type X * assumed
        manual-minutes for X) / 60. The system's own time-to-complete an
        action is a few seconds, negligible next to the manual estimate, so
        it's dropped from the subtraction rather than tracked precisely."""
        actions = list(minutes_by_action.keys())
        if not actions:
            return 0.0
        placeholders = ','.join('?' for _ in actions)
        sql = f'SELECT action, COUNT(*) AS c FROM activity_logs WHERE action IN ({placeholders}) AND status=? GROUP BY action'
        conn = get_conn()
        rows = conn.execute(sql, [*actions, status]).fetchall()
        conn.close()
        total_minutes = sum(r['c'] * minutes_by_action.get(r['action'], 0) for r in rows)
        return round(total_minutes / 60, 1)

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
