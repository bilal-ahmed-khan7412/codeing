from pathlib import Path
import re

root = Path(__file__).resolve().parent
web_dir = root / 'web'
readme = root / 'README.md'

if not web_dir.exists():
    raise SystemExit('web folder not found. Run this patch inside intern_tracker_system_v0.')

pages = ['chat.html', 'users.html', 'logs.html', 'tasks.html', 'profile.html', 'index.html']

nav_js = r'''
<script id="v69-consistent-profile-nav">
async function v69ConsistentProfileNav(){
  try{
    const r = await fetch('/api/me');
    const d = await r.json();
    const user = d.user || null;
    if(!user) return;
    const role = String(user.role || '').toLowerCase();

    let nav = document.querySelector('header .nav') || document.querySelector('header div:last-child') || document.querySelector('header');
    if(!nav) return;

    function hasHref(href){ return !!document.querySelector('header a[href="' + href + '"]'); }
    function addLink(href, text){
      if(hasHref(href)) return;
      const a = document.createElement('a');
      a.href = href;
      a.textContent = text;
      a.style.color = 'white';
      a.style.fontWeight = '700';
      a.style.marginLeft = '14px';
      nav.appendChild(a);
    }

    // Profile should be visible to every logged-in role.
    addLink('/profile', 'Profile');

    // Logout should also be consistently visible.
    addLink('/logout', 'Logout');

    // Normal users should not see governance/admin navigation.
    if(role === 'user'){
      document.querySelectorAll('header a[href="/users"], header a[href="/logs"], header a[href="/tasks"]').forEach(a => a.remove());
    }

    // Admin and Super Admin should have governance links available on main pages.
    if(role === 'admin' || role === 'super admin'){
      addLink('/users', 'Users');
      addLink('/logs', 'Logs');
      addLink('/tasks', 'Tasks');
    }
  }catch(e){
    // Route-level permissions remain the security layer.
  }
}
v69ConsistentProfileNav();
</script>
'''

for name in pages:
    p = web_dir / name
    if not p.exists():
        continue
    s = p.read_text(encoding='utf-8')

    # Remove older duplicate nav filters and previous v69 if reapplying.
    s = re.sub(r'<script>\s*async function v61HideAdminLinks\(\).*?</script>', '', s, flags=re.S)
    s = re.sub(r'<script>\s*async function v65HideAdminAndTaskLinks\(\).*?</script>', '', s, flags=re.S)
    s = re.sub(r'<script id="v66-role-nav-filter">.*?</script>', '', s, flags=re.S)
    s = re.sub(r'<script id="v69-consistent-profile-nav">.*?</script>', '', s, flags=re.S)

    # If a page has no Profile link in static HTML, add it before Logout where possible.
    if '/profile' not in s and '/logout' in s:
        s = re.sub(r'(<a[^>]+href=["\']/logout["\'][^>]*>\s*Logout\s*</a>)', r'<a href="/profile">Profile</a>\1', s, count=1, flags=re.I)

    if '</body>' in s:
        s = s.replace('</body>', nav_js + '\n</body>')
    else:
        s += nav_js
    p.write_text(s, encoding='utf-8')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.69 Consistent Profile navigation

- Profile link is now consistently visible for every logged-in role across main pages.
- Logout link is also ensured in the header.
- Normal Users still do not see Users, Logs, or Tasks.
- Admin and Super Admin see Users, Logs, Tasks, Profile, and Logout.
- Route permissions remain the actual security layer; this patch standardizes the navbar UI.
''', encoding='utf-8')

print('v0.69 consistent profile navbar patch applied successfully.')
