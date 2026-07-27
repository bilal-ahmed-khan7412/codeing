from pathlib import Path

root = Path(__file__).resolve().parent
plan_service = root / 'tracker_services' / 'plan_service.py'
readme = root / 'README.md'

if not plan_service.exists():
    raise SystemExit('tracker_services/plan_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = plan_service.read_text(encoding='utf-8')

# Blank remarks in schedules generated from edited/LLM preview.
s = s.replace(
    "tasks.append([current, week, item['theme'], item['task'], 'Pending', item.get('notes', '')])",
    "tasks.append([current, week, item['theme'], item['task'], 'Pending', ''])"
)

# Blank remarks in schedules generated directly from plan rows.
s = s.replace(
    "tasks.append([current, week, item['theme'], item['task'], 'Pending', item.get('notes','')])",
    "tasks.append([current, week, item['theme'], item['task'], 'Pending', ''])"
)

# If there are spacing variants, handle them too.
s = s.replace(
    "tasks.append([current, week, item['theme'], item['task'], 'Pending', item.get('notes', '')])",
    "tasks.append([current, week, item['theme'], item['task'], 'Pending', ''])"
)
s = s.replace(
    "tasks.append([current, week, item['theme'], item['task'], 'Pending', item.get('notes','')])",
    "tasks.append([current, week, item['theme'], item['task'], 'Pending', ''])"
)

plan_service.write_text(s, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.39 Blank daily task remarks for LLM-generated intern sheets

- Daily task `Remarks` are now left blank when creating an intern from a plan or LLM-generated schedule preview.
- LLM notes are still used for weekly/small project descriptions where useful.
- Remarks are reserved for manager/user updates after the workbook is created.
''', encoding='utf-8')

print('v0.39 blank daily task remarks patch applied successfully.')
