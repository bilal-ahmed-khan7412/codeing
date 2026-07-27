from pathlib import Path

ROOT = Path(".")
WEB_APP = ROOT / "web_app.py"
WEB_DIR = ROOT / "web"

if not WEB_APP.exists():
    raise FileNotFoundError("web_app.py not found. Run this patch from project root.")

WEB_DIR.mkdir(exist_ok=True)


def build_page(title, default_role, cards):
    cards_html = ""

    for card in cards:
        btn_class = "btn " + card.get("class", "")

        cards_html += f"""
        <div class="card">
            <h3>{card['title']}</h3>
            <p class="muted">{card['desc']}</p>
            <card['href']}
                {card['button']}
            </a>
        </div>
        """

    return f"""<!doctype html>
<html>
<head>
<title>{title}</title>

<style>
body {{
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f4f6fb;
    color: #1f2937;
}}

header {{
    background: #305496;
    color: white;
    padding: 20px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

header h1 {{
    margin: 0;
    font-size: 22px;
}}

header a {{
    color: white;
    font-weight: 700;
    margin-left: 16px;
    text-decoration: none;
}}

main {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 28px;
}}

.hero {{
    background: white;
    border: 1px solid #d9e2ef;
    border-radius: 18px;
    padding: 28px;
    box-shadow: 0 6px 22px rgba(15, 23, 42, .08);
    margin-bottom: 22px;
}}

.hero h2 {{
    margin: 0 0 10px;
    color: #305496;
}}

.muted {{
    color: #64748b;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 16px;
}}

.card {{
    background: white;
    border: 1px solid #d9e2ef;
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 4px 16px rgba(15, 23, 42, .06);
}}

.card h3 {{
    margin: 0 0 8px;
    color: #1f3f75;
}}

.btn {{
    display: inline-block;
    background: #305496;
    color: white;
    text-decoration: none;
    padding: 10px 14px;
    border-radius: 10px;
    font-weight: 700;
    margin-top: 10px;
}}

.secondary {{
    background: #eef2ff;
    color: #305496;
}}

.role-badge {{
    display: inline-block;
    background: #e0f2fe;
    color: #075985;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 13px;
}}
</style>

</head>

<body>

<header>
    <h1>{title}</h1>

    <div>
        /profile
        /logoutLogout</a>
    </div>
</header>

<main>

<section class="hero">
    <h2>Welcome, <span id="userName">User</span></h2>

    <p>
        <span class="role-badge" id="userRole">{default_role}</span>
    </p>

    <p class="muted" id="userEmail"></p>

    <p class="muted">
        Use the options below to navigate through the Intern Tracker System.
    </p>
</section>

<section class="grid">
{cards_html}
</section>

</main>

<script>
async function loadMe() {{
    try {{
        const r = await fetch('/api/me');
        const d = await r.json();
        const u = d.user || {{}};

        document.getElementById('userName').textContent =
            u.name || 'User';

        document.getElementById('userEmail').textContent =
            u.email || '';

        document.getElementById('userRole').textContent =
            u.role || '{default_role}';

    }} catch (e) {{
        console.error(e);
    }}
}}

loadMe();
</script>

</body>
</html>
"""


super_admin_cards = [
    {
        "title": "Chat Assistant",
        "desc": "Create plans, add interns, generate summaries, and manage tracker operations.",
        "href": "/chat",
        "button": "Open Chat"
    },
    {
        "title": "User Management",
        "desc": "Approve users, manage roles, activate or deactivate accounts.",
        "href": "/users",
        "button": "Manage Users"
    },
    {
        "title": "Audit Logs",
        "desc": "Review system activity, user actions, approvals, and exported records.",
        "href": "/logs",
        "button": "View Logs"
    },
    {
        "title": "Tasks",
        "desc": "Manage governance or admin-level user tasks.",
        "href": "/tasks",
        "button": "Open Tasks"
    },
    {
        "title": "Evaluation",
        "desc": "Upload tracker and evaluation files, score interns, and finalize evaluation reports.",
        "href": "/evaluation",
        "button": "Open Evaluation"
    },
]

admin_cards = [
    {
        "title": "Chat Assistant",
        "desc": "Use chat to create plans, add interns, update trackers, and generate summaries.",
        "href": "/chat",
        "button": "Open Chat"
    },
    {
        "title": "User Management",
        "desc": "Approve and manage normal users based on admin permissions.",
        "href": "/users",
        "button": "Manage Users"
    },
    {
        "title": "Audit Logs",
        "desc": "Review operational logs and user activity.",
        "href": "/logs",
        "button": "View Logs"
    },
    {
        "title": "Tasks",
        "desc": "Manage admin task workflows.",
        "href": "/tasks",
        "button": "Open Tasks"
    },
    {
        "title": "Evaluation",
        "desc": "Run intern evaluation workflow and generate evaluation output files.",
        "href": "/evaluation",
        "button": "Open Evaluation"
    },
]

user_cards = [
    {
        "title": "Chat Assistant",
        "desc": "Ask for summaries and perform allowed tracker operations using the assistant.",
        "href": "/chat",
        "button": "Open Chat"
    },
    {
        "title": "Profile",
        "desc": "View or update your own profile information.",
        "href": "/profile",
        "button": "Open Profile",
        "class": "secondary"
    },
]

(WEB_DIR / "super_admin_home.html").write_text(
    build_page("Super Admin Dashboard", "Super Admin", super_admin_cards),
    encoding="utf-8"
)

(WEB_DIR / "admin_home.html").write_text(
    build_page("Admin Dashboard", "Admin", admin_cards),
    encoding="utf-8"
)

(WEB_DIR / "user_home.html").write_text(
    build_page("User Dashboard", "User", user_cards),
    encoding="utf-8"
)

print("[OK] Landing pages created.")


# ------------------------------------------------------------
# Patch web_app.py
# ------------------------------------------------------------

src = WEB_APP.read_text(encoding="utf-8")

backup = WEB_APP.with_suffix(".py.bak_v107")
if not backup.exists():
    backup.write_text(src, encoding="utf-8")
    print("[OK] web_app.py backup created.")


role_routes = """
def redirect_by_role(user):
    role = (user or {}).get('role', '')
    if role == 'Super Admin':
        return RedirectResponse('/super-admin')
    if role == 'Admin':
        return RedirectResponse('/admin')
    return RedirectResponse('/user')


@app.get('/super-admin', response_class=HTMLResponse)
def super_admin_home(request: Request):
    user = require_login(request)
    if user.get('role') != 'Super Admin':
        return redirect_by_role(user)
    return (BASE_DIR / 'web' / 'super_admin_home.html').read_text(encoding='utf-8')


@app.get('/admin', response_class=HTMLResponse)
def admin_home(request: Request):
    user = require_login(request)
    if user.get('role') == 'Super Admin':
        return RedirectResponse('/super-admin')
    if user.get('role') != 'Admin':
        return RedirectResponse('/user')
    return (BASE_DIR / 'web' / 'admin_home.html').read_text(encoding='utf-8')


@app.get('/user', response_class=HTMLResponse)
def user_home(request: Request):
    user = require_login(request)
    if user.get('role') == 'Super Admin':
        return RedirectResponse('/super-admin')
    if user.get('role') == 'Admin':
        return RedirectResponse('/admin')
    return (BASE_DIR / 'web' / 'user_home.html').read_text(encoding='utf-8')


@app.get('/forms', response_class=HTMLResponse)
def old_forms_hidden(request: Request):
    user = current_user_from_request(request)
    if not user:
        return RedirectResponse('/login')
    return redirect_by_role(user)

"""

if "def redirect_by_role(user):" not in src:
    marker = "def require_login(request: Request):"
    idx = src.find(marker)

    if idx == -1:
        raise RuntimeError("Could not find require_login function.")

    next_def = src.find("\ndef ", idx + len(marker))

    if next_def == -1:
        raise RuntimeError("Could not find insertion point after require_login.")

    src = src[:next_def] + "\n" + role_routes + "\n" + src[next_def:]
    print("[OK] Added role-based landing routes.")
else:
    print("[SKIP] Role routes already exist.")


old_home = """@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE_DIR / "web" / "index.html").read_text(encoding="utf-8")"""

new_home = """@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = current_user_from_request(request)
    if not user:
        return RedirectResponse('/login')
    return redirect_by_role(user)"""

if old_home in src:
    src = src.replace(old_home, new_home)
    print("[OK] Root page now redirects by role.")
elif "def home(request: Request):" in src and "redirect_by_role(user)" in src:
    print("[SKIP] Root route already redirects by role.")
else:
    print("[WARN] Could not replace root route automatically. Check web_app.py manually.")

WEB_APP.write_text(src, encoding="utf-8")

print("\nPatch v107 applied successfully.")
print("Login will now redirect users to Super Admin, Admin, or User landing pages.")