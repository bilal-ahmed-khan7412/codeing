from pathlib import Path
import re

root = Path(__file__).resolve().parent
web_dir = root / 'web'
chat_html = web_dir / 'chat.html'
users_html = web_dir / 'users.html'
logs_html = web_dir / 'logs.html'
tasks_html = web_dir / 'tasks.html'
readme = root / 'README.md'

if not web_dir.exists():
    raise SystemExit('web folder not found. Run this patch inside intern_tracker_system_v0.')

# Hide links to the forms page from user-facing navigation.
# The forms page itself is not deleted and direct / URL can still be opened manually.
for p in [chat_html, users_html, logs_html, tasks_html]:
    if not p.exists():
        continue
    s = p.read_text(encoding='utf-8')

    # Remove common Forms anchor variations.
    s = re.sub(r'<a[^>]+href=["\']/["\'][^>]*>\s*Forms\s*</a>', '', s, flags=re.I)
    s = re.sub(r'<a[^>]+href=["\']/["\'][^>]*>\s*Back to Forms\s*</a>', '', s, flags=re.I)

    # Remove extra whitespace left in nav/header areas.
    s = re.sub(r'(<div class="nav">)\s+', r'\1', s)
    s = re.sub(r'\s+(</div>)', r'\1', s)

    p.write_text(s, encoding='utf-8')

# On index/forms page, add a small notice that forms are legacy/direct-access only.
index = web_dir / 'index.html'
if index.exists():
    s = index.read_text(encoding='utf-8')
    if 'Forms page is kept for admin/direct access' not in s:
        s = s.replace(
            '<p>Button/form interface over the same command engine used by CLI and future LLM chat.</p>',
            '<p>Forms page is kept for admin/direct access. Normal workflow should use the Chat Assistant.</p>'
        )
    index.write_text(s, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.50 Hide Forms links from user-facing UI

- Removed visible navigation links to the old Forms page from Chat, Users, Logs, and Tasks pages.
- The Forms page is not deleted. Direct `/` access still works for admin/debug use.
- The normal user-facing workflow is now Chat Assistant first.
''', encoding='utf-8')

print('v0.50 hide forms links patch applied successfully.')
