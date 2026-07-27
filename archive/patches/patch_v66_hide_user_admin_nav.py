from pathlib import Path

root = Path(__file__).resolve().parent
web_dir = root / 'web'
readme = root / 'README.md'

if not web_dir.exists():
    raise SystemExit('web folder not found. Run this patch inside intern_tracker_system_v0.')

pages = ['chat.html', 'tasks.html', 'logs.html', 'users.html', 'profile.html', 'index.html']

hide_js = r'''
<script id="v66-role-nav-filter">
async function v66RoleNavFilter(){
  try{
    const r = await fetch('/api/me');
    const d = await r.json();
    const role = String((d.user && d.user.role) || '').toLowerCase();
    if(role === 'user'){
      document.querySelectorAll('a[href="/users"], a[href="/logs"], a[href="/tasks"]').forEach(a => a.remove());
    }
  }catch(e){
    // If user info cannot be loaded, leave server-side route protection as fallback.
  }
}
v66RoleNavFilter();
</script>
'''

for name in pages:
    p = web_dir / name
    if not p.exists():
        continue
    s = p.read_text(encoding='utf-8')
    # Remove older duplicate role-filter snippets to avoid stacking multiple functions.
    import re
    s = re.sub(r'<script>\s*async function v61HideAdminLinks\(\).*?</script>', '', s, flags=re.S)
    s = re.sub(r'<script>\s*async function v65HideAdminAndTaskLinks\(\).*?</script>', '', s, flags=re.S)
    s = re.sub(r'<script id="v66-role-nav-filter">.*?</script>', '', s, flags=re.S)
    if '</body>' in s:
        s = s.replace('</body>', hide_js + '\n</body>')
    else:
        s += hide_js
    p.write_text(s, encoding='utf-8')

# Also add a server hardening note by denying normal users at /users and /logs is already enforced
# by can_manage_users/can_view_logs in v61/v65 permissions. This patch focuses on visible navbar.

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.66 Hide admin navigation for normal Users

- Normal `User` role now has `/users`, `/logs`, and `/tasks` links removed from visible navigation.
- Applied across Chat, Profile, Tasks, Logs, Users, and legacy Forms pages.
- Server-side route permissions remain the real security layer; this patch cleans the UI so normal users do not see admin/governance navigation.
''', encoding='utf-8')

print('v0.66 hide normal-user admin navbar patch applied successfully.')
