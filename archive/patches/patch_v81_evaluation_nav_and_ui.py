"""
Patch v0.81 - Evaluation navbar + professional UI

Apply from the root of the app that serves /evaluation:
    python patch_v81_evaluation_nav_and_ui.py

Purpose:
- Add Evaluation as a first-class navbar link for Admin/Super Admin.
- Hide Evaluation from normal User.
- Improve /evaluation page layout and review readability.
- Keep overall-only evaluation behavior from v0.76/v0.80.
- Keep AI rationale/reason hidden from the page.
- Keep workbook unchanged until Finalize Evaluation is clicked.
- UI-first patch with best-effort backend route protection if a FastAPI app file is found.

Notes:
- This patch does not hardcode any intern name.
- This patch does not change scoring rubric or scoring method.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent

PAGE_CANDIDATES = [
    ROOT / "web" / "evaluation.html",
    ROOT / "evaluation.html",
    ROOT / "templates" / "evaluation.html",
]

APP_CANDIDATES = [
    ROOT / "web_app.py",
    ROOT / "app.py",
    ROOT / "main.py",
]

page = next((p for p in PAGE_CANDIDATES if p.exists()), None)
if page is None:
    raise SystemExit("Could not find evaluation.html. Run this patch from the app root folder that contains /evaluation.")

html = page.read_text(encoding="utf-8")

block = r'''

<!-- v0.81 evaluation navbar + professional UI -->
<style id="v81-evaluation-ui-style">
  :root {
    --v81-primary: #305496;
    --v81-primary-dark: #1f3f75;
    --v81-bg: #f4f6fb;
    --v81-card: #ffffff;
    --v81-border: #d9e2ef;
    --v81-muted: #64748b;
    --v81-text: #1f2937;
    --v81-success: #166534;
    --v81-warning: #92400e;
  }

  body {
    background: var(--v81-bg) !important;
    color: var(--v81-text) !important;
  }

  .v81-eval-nav {
    background: var(--v81-primary);
    color: white;
    padding: 14px 22px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.14);
    position: sticky;
    top: 0;
    z-index: 9999;
  }

  .v81-eval-nav-title {
    font-weight: 800;
    letter-spacing: 0.2px;
    white-space: nowrap;
  }

  .v81-eval-nav-links {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .v81-eval-nav a {
    color: white;
    text-decoration: none;
    font-weight: 700;
    font-size: 14px;
    opacity: 0.95;
  }

  .v81-eval-nav a:hover {
    text-decoration: underline;
    opacity: 1;
  }

  .v81-eval-shell {
    max-width: 1320px;
    margin: 0 auto;
    padding: 18px;
  }

  .v81-eval-hero {
    background: linear-gradient(135deg, #305496, #1d4ed8);
    color: white;
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 16px;
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.16);
  }

  .v81-eval-hero h1,
  .v81-eval-hero h2,
  .v81-eval-hero h3 {
    margin-top: 0;
    color: white !important;
  }

  .v81-eval-hero p {
    margin-bottom: 0;
    opacity: 0.92;
  }

  .v81-eval-grid {
    display: grid;
    grid-template-columns: minmax(320px, 420px) minmax(420px, 1fr);
    gap: 16px;
    align-items: start;
  }

  .v81-panel,
  .v81-review-panel,
  .v81-card {
    background: var(--v81-card);
    border: 1px solid var(--v81-border);
    border-radius: 14px;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
  }

  .v81-panel,
  .v81-review-panel {
    padding: 16px;
  }

  .v81-sticky {
    position: sticky;
    top: 78px;
  }

  .v81-section-title {
    margin: 0 0 10px;
    color: var(--v81-primary-dark);
    font-size: 18px;
    font-weight: 800;
  }

  .v81-muted {
    color: var(--v81-muted);
    font-size: 13px;
  }

  .v81-status-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin: 10px 0;
  }

  .v81-badge {
    border-radius: 999px;
    padding: 4px 9px;
    background: #e0f2fe;
    color: #075985;
    font-size: 12px;
    font-weight: 800;
  }

  .v81-badge-warning {
    background: #fffbeb;
    color: var(--v81-warning);
  }

  .v81-badge-success {
    background: #dcfce7;
    color: var(--v81-success);
  }

  .v81-review-panel {
    min-height: 360px;
  }

  .v81-review-panel details,
  details.v81-criterion-card {
    background: #ffffff;
    border: 1px solid var(--v81-border);
    border-radius: 12px;
    margin: 10px 0;
    padding: 10px 12px;
  }

  .v81-review-panel summary,
  details.v81-criterion-card summary {
    cursor: pointer;
    color: var(--v81-primary-dark);
    font-weight: 800;
  }

  .v81-score-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(120px, 1fr));
    gap: 10px;
    margin: 10px 0;
  }

  .v81-score-tile {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    background: #f8fafc;
    padding: 10px;
  }

  .v81-score-label {
    color: var(--v81-muted);
    font-size: 12px;
    font-weight: 700;
  }

  .v81-score-value {
    color: #0f172a;
    font-size: 20px;
    font-weight: 900;
  }

  .v81-finalize-bar {
    position: sticky;
    bottom: 0;
    background: rgba(255,255,255,0.96);
    border-top: 1px solid var(--v81-border);
    padding: 12px 0 0;
    margin-top: 14px;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
    backdrop-filter: blur(6px);
  }

  button,
  input[type="button"],
  input[type="submit"] {
    border-radius: 10px !important;
    font-weight: 800 !important;
  }

  #v78EvalDebugButton,
  #v79EvalDebugButton {
    display: none !important;
  }

  /* Keep private AI reasoning hidden. */
  .ai-reason,
  .ai-rationale,
  .reason,
  .reason-text,
  .rationale,
  .rationale-text,
  [data-ai-reason],
  [data-reason],
  [data-rationale] {
    display: none !important;
  }

  @media (max-width: 980px) {
    .v81-eval-grid {
      grid-template-columns: 1fr;
    }
    .v81-sticky {
      position: static;
    }
    .v81-score-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
<script id="v81-evaluation-ui-script">
(function(){
  function norm(text){ return String(text || '').replace(/\s+/g, ' ').trim(); }
  function normLower(text){ return norm(text).toLowerCase(); }

  async function getCurrentUser(){
    try{
      const r = await fetch('/api/me');
      const d = await r.json();
      return d.user || null;
    }catch(e){ return null; }
  }

  function ensureNavbar(user){
    if(document.getElementById('v81EvalNav')) return;
    const role = normLower(user && user.role);
    const isAdmin = role === 'admin' || role === 'super admin';

    const nav = document.createElement('div');
    nav.id = 'v81EvalNav';
    nav.className = 'v81-eval-nav';
    nav.innerHTML = '<div class="v81-eval-nav-title">Intern Evaluation</div><div class="v81-eval-nav-links" id="v81EvalNavLinks"></div>';

    const links = nav.querySelector('#v81EvalNavLinks');
    function add(href, text){
      const a = document.createElement('a');
      a.href = href;
      a.textContent = text;
      links.appendChild(a);
    }

    add('/chat', 'Chat');
    if(isAdmin){
      add('/evaluation', 'Evaluation');
      add('/users', 'Users');
      add('/logs', 'Logs');
      add('/tasks', 'Tasks');
    }
    add('/profile', 'Profile');
    add('/logout', 'Logout');

    document.body.insertBefore(nav, document.body.firstChild);
  }

  function protectEvaluationForNormalUser(user){
    const role = normLower(user && user.role);
    if(role === 'user'){
      const warning = document.createElement('div');
      warning.style.padding = '18px';
      warning.style.margin = '18px';
      warning.style.border = '1px solid #fecaca';
      warning.style.borderRadius = '12px';
      warning.style.background = '#fef2f2';
      warning.style.color = '#991b1b';
      warning.style.fontWeight = '700';
      warning.textContent = 'Evaluation is available to Admin and Super Admin only. Redirecting to Chat...';
      document.body.innerHTML = '';
      document.body.appendChild(warning);
      setTimeout(function(){ location.href = '/chat'; }, 900);
    }
  }

  function wrapMainContent(){
    if(document.querySelector('.v81-eval-shell')) return;
    const nav = document.getElementById('v81EvalNav');
    const shell = document.createElement('main');
    shell.className = 'v81-eval-shell';

    const nodes = Array.from(document.body.children).filter(function(el){
      return el !== nav && el.tagName !== 'SCRIPT' && el.tagName !== 'STYLE';
    });

    const hero = document.createElement('section');
    hero.className = 'v81-eval-hero';
    hero.innerHTML = '<h2>Evaluation Review</h2><p>Upload/select the workbook, generate the review, edit final scores if needed, then finalize. Workbook changes are written only when Finalize Evaluation is clicked.</p>';
    shell.appendChild(hero);

    const grid = document.createElement('section');
    grid.className = 'v81-eval-grid';

    const left = document.createElement('aside');
    left.className = 'v81-panel v81-sticky';
    left.innerHTML = '<h3 class="v81-section-title">Evaluation Setup</h3><div class="v81-status-row"><span class="v81-badge">Overall basis</span><span class="v81-badge v81-badge-warning">Draft until finalized</span></div>';

    const right = document.createElement('section');
    right.className = 'v81-review-panel';
    right.innerHTML = '<h3 class="v81-section-title">Review</h3>';

    // Heuristic: controls/forms/upload buttons go left; review/question cards go right.
    nodes.forEach(function(el){
      const text = normLower(el.textContent || '');
      const html = String(el.outerHTML || '').toLowerCase();
      const looksReview = text.includes('criterion') || text.includes('scoring basis') || text.includes('finalize evaluation') || text.includes('daily score') || text.includes('weekly score') || html.includes('finalizeeval');
      const looksSetup = html.includes('upload') || html.includes('file') || text.includes('select') || text.includes('intern') || text.includes('evaluation sheet') || text.includes('generate');
      if(looksReview && !looksSetup){
        right.appendChild(el);
      } else {
        left.appendChild(el);
      }
    });

    grid.appendChild(left);
    grid.appendChild(right);
    shell.appendChild(grid);
    document.body.appendChild(shell);
  }

  function styleCriteriaCards(){
    Array.from(document.querySelectorAll('body *')).forEach(function(el){
      const t = normLower(el.textContent);
      if(t.startsWith('criterion ') && !el.closest('.v81-criterion-card')){
        const parent = el.closest('section, article, div, li') || el;
        if(parent && !parent.classList.contains('v81-review-panel')){
          parent.classList.add('v81-card');
          parent.style.padding = parent.style.padding || '12px';
          parent.style.margin = parent.style.margin || '10px 0';
        }
      }
    });
  }

  function ensureFinalizeBar(){
    if(document.querySelector('.v81-finalize-bar')) return;
    const finalizeButton = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"]')).find(function(btn){
      return normLower(btn.textContent || btn.value).includes('finalize');
    });
    if(!finalizeButton) return;
    const bar = document.createElement('div');
    bar.className = 'v81-finalize-bar';
    const note = document.createElement('div');
    note.className = 'v81-muted';
    note.textContent = 'Workbook is not updated until Finalize Evaluation is clicked.';
    finalizeButton.parentElement.insertBefore(bar, finalizeButton);
    bar.appendChild(note);
    bar.appendChild(finalizeButton);
  }

  function hideReasonBlocks(){
    Array.from(document.querySelectorAll('.ai-reason,.ai-rationale,.reason,.reason-text,.rationale,.rationale-text,[data-ai-reason],[data-reason],[data-rationale]')).forEach(function(el){
      el.style.display = 'none';
    });
  }

  async function boot(){
    const user = await getCurrentUser();
    ensureNavbar(user);
    protectEvaluationForNormalUser(user);
    if(normLower(user && user.role) === 'user') return;
    wrapMainContent();
    styleCriteriaCards();
    ensureFinalizeBar();
    hideReasonBlocks();
  }

  document.addEventListener('DOMContentLoaded', boot);
  setTimeout(boot, 150);
  setTimeout(boot, 700);
  const mo = new MutationObserver(function(){
    clearTimeout(window.__v81EvalUiTimer);
    window.__v81EvalUiTimer = setTimeout(function(){
      styleCriteriaCards();
      ensureFinalizeBar();
      hideReasonBlocks();
    }, 120);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
'''

if "v81-evaluation-ui-script" not in html:
    if "</body>" in html:
        html = html.replace("</body>", block + "\n</body>", 1)
    else:
        html += block
    page.write_text(html, encoding="utf-8")
    print(f"Updated evaluation UI: {page}")
else:
    print("v0.81 evaluation UI patch already applied.")

# Best-effort backend protection for common FastAPI route shape.
app_file = next((p for p in APP_CANDIDATES if p.exists()), None)
backend_note = "No app file found for backend route protection. UI protection was added."
if app_file:
    app = app_file.read_text(encoding="utf-8")
    if "v0.81 evaluation route protection" not in app:
        # Add can_view_logs import fallback if permissions helpers exist. Evaluation follows Admin/Super Admin governance.
        if "from tracker_auth.permissions" in app and "can_view_logs" not in app:
            app = re.sub(r"from tracker_auth\.permissions import ([^\n]+)", lambda m: "from tracker_auth.permissions import " + m.group(1).rstrip() + ", can_view_logs", app, count=1)

        # Patch simple evaluation route function if present.
        route_pattern = re.compile(
            r"(@app\.get\(['\"]\/evaluation['\"].*?\)\s*\n\s*def\s+evaluation_page\s*\(request:\s*Request\):\s*\n)(.*?)(?=\n@app\.|\n\s*def\s+|\Z)",
            re.S,
        )
        m = route_pattern.search(app)
        if m and "v0.81 evaluation route protection" not in m.group(0):
            body = """    # v0.81 evaluation route protection\n    user = current_user_from_request(request)\n    if not user:\n        return RedirectResponse('/login')\n    if user.get('role') not in {'Admin', 'Super Admin'}:\n        return RedirectResponse('/chat')\n    return (BASE_DIR / 'web' / 'evaluation.html').read_text(encoding='utf-8')\n"""
            app = app[:m.start()] + m.group(1) + body + app[m.end():]
            backend_note = f"Patched /evaluation route protection in {app_file.name}."
        else:
            backend_note = f"Could not safely patch /evaluation route in {app_file.name}; UI protection was added."

        app_file.write_text(app, encoding="utf-8")

report = ROOT / "v81_evaluation_nav_ui_report.txt"
report.write_text(
    "v0.81 Evaluation navbar + UI patch applied.\n"
    f"Evaluation page: {page}\n"
    f"Backend protection: {backend_note}\n"
    "Admin/Super Admin should see Evaluation in navbar. Normal User should not.\n",
    encoding="utf-8",
)

print(backend_note)
print(f"Report: {report}")
