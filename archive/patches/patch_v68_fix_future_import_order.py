from pathlib import Path

root = Path(__file__).resolve().parent
web_app = root / 'web_app.py'
readme = root / 'README.md'

if not web_app.exists():
    raise SystemExit('web_app.py not found. Run this patch inside intern_tracker_system_v0.')

s = web_app.read_text(encoding='utf-8')
lines = s.splitlines()

future_line = 'from __future__ import annotations'
# Remove all duplicate future imports from their current positions.
lines = [line for line in lines if line.strip() != future_line]

# Preserve shebang/encoding comments at the very top if present.
insert_idx = 0
if lines and lines[0].startswith('#!'):
    insert_idx = 1
if len(lines) > insert_idx and ('coding' in lines[insert_idx] or 'coding:' in lines[insert_idx]):
    insert_idx += 1

lines.insert(insert_idx, future_line)

# Remove duplicate simple imports that may have been added multiple times by patches.
seen = set()
cleaned = []
for line in lines:
    key = line.strip()
    if key in {'import secrets', 'import string'}:
        if key in seen:
            continue
        seen.add(key)
    cleaned.append(line)

web_app.write_text('\n'.join(cleaned) + '\n', encoding='utf-8')

# Compile check.
try:
    import py_compile
    py_compile.compile(str(web_app), doraise=True)
except Exception as e:
    raise SystemExit(f'web_app.py still has a compile issue: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.68 Fix Python future import order

- Fixed server startup error:
  `SyntaxError: from __future__ imports must occur at the beginning of the file`.
- Moves `from __future__ import annotations` back to the top of `web_app.py` after previous patches inserted imports above it.
''', encoding='utf-8')

print('v0.68 fixed web_app.py future import order successfully.')
