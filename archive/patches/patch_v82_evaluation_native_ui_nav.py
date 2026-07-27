"""
Patch v0.82 - Evaluation-native UI cleanup + admin navbar only

Apply from the root of the app that serves /evaluation:
    python patch_v82_evaluation_native_ui_nav.py

Purpose:
- Undo the v0.81 attempt to force the general app "review panel" layout onto /evaluation.
- Keep /evaluation as its own workflow: Upload -> Match Intern -> Questions -> Review -> Download.
- Add a clean Evaluation navbar link for Admin/Super Admin only.
- Hide Evaluation/Users/Logs/Tasks links for normal User.
- Preserve existing evaluation steps, cards, questions, finalize behavior, scoring, and workbook write flow.
- Keep overall-only evaluation behavior from v0.76/v0.80.
- Keep AI reason/rationale hidden.
- No intern name hardcoded.
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

page = next((p for p in PAGE_CANDIDATES if p.exists()), None)
if page is None:
    raise SystemExit("Could not find evaluation.html. Run this patch from the app root folder that contains /evaluation.")

html = page.read_text(encoding="utf-8")

# Remove the v81 layout forcing block. It was too aggressive for the evaluation-specific workflow.
html = re.sub(r'\n?<!-- v0\.81 evaluation navbar \+ professional UI -->.*?<script id="v81-evaluation-ui-script">.*?</script>\s*', '\n', html, flags=re.S)

block = r'''

<!-- v0.82 evaluation-native navbar and UI polish -->
<style id="v82-evaluation-native-style">
  :root {
    --eval-primary: #305496;
    --eval-primary-dark: #1f3f75;
    --eval-bg: #f4f6fb;
    --eval-card: #ffffff;
    --eval-border: #d9e2ef;
    --eval-muted: #64748b;
    --eval-text: #1f2937;
  }

  body {
    background: var(--eval-bg) !important;
    color: var(--eval-text) !important;
  }

  .v82-eval-nav {
    background: var(--eval-primary);
    color: white;
    padding: 14px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    border-bottom: 1px solid rgba(255,255,255,0.18);
    box-shadow: 0 2px 10px rgba(15,23,42,0.12);
    position: sticky;
    top: 0;
    z-index: 10000;
  }

  .v82-eval-nav-title {
    font-weight: 900;
    letter-spacing: 0.2px;
    white-space: nowrap;
  }

  .v82-eval-nav-links {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .v82-eval-nav a {
    color: white;
    font-weight: 800;
    text-decoration: none;
    font-size: 14px;
  }

  .v82-eval-nav a:hover {
    text-decoration: underline;
  }

  .v82-eval-note {
    max-width: 980px;
    margin: 14px auto 0;
    padding: 10px 14px;
    border: 1px solid #bfdbfe;
    background: #eff6ff;
    border-radius: 12px;
    color: #1e3a8a;
    font-size: 13px;
    font-weight: 700;
  }

  /* Do not restructure the page. Only polish the existing evaluation workflow. */
  main,
  .container,
  .page,
  .content,
  #app {
    max-width: 1180px;
  }

  /* Existing step pills/buttons keep their workflow identity. */
  button,
  input[type="button"],
  input[type="submit"] {
    border-radius: 10px !important;
    font-weight: 800 !important;
  }

  /* Soften cards without changing layout. */
  .card,
  section,
  article,
  .panel,
  .question-card,
  .criterion-card {
    border-radius: 14px;
  }

  /* Keep scoring basis compact. */
  .v76-overall-card {
    box-shadow: none !important;
    margin: 10px 0 !important;
  }

  .v76-progress-grid {
    grid-template-columns: repeat(2, minmax(180px, 1fr)) !important;
  }

  /* Remove debug buttons from production-looking UI if v78/v79 were applied. */
  #v78EvalDebugButton,
  #v79EvalDebugButton {
    display: none !important;
  }

  /* Keep AI/private reasoning hidden. */
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

  @media (max-width: 760px) {
    .v82-eval-nav {
      align-items: flex-start;
      flex-direction: column;
    }
    .v82-eval-nav-links {
      justify-content: flex-start;
    }
    .v76-progress-grid {
      grid-template-columns: 1fr !important;
    }
  }
</style>
<script id="v82-evaluation-native-script">
(function(){
  function norm(text){ return String(text || '').replace(/\s+/g, ' ').trim(); }
  function lower(text){ return norm(text).toLowerCase(); }

  async function getUser(){
    try {
      const r = await fetch('/api/me');
      const d = await r.json();
      return d.user || null;
    } catch(e) {
      return null;
    }
  }

  function removeOldNavs(){
    document.querySelectorAll('#v81EvalNav, #v82EvalNav').forEach(function(el){ el.remove(); });
  }

  function ensureNav(user){
    removeOldNavs();
    const role = lower(user && user.role);
    const isAdmin = role === 'admin' || role === 'super admin';

    const nav = document.createElement('div');
    nav.id = 'v82EvalNav';
    nav.className = 'v82-eval-nav';

    const title = document.createElement('div');
    title.className = 'v82-eval-nav-title';
    title.textContent = 'Intern Evaluation';

    const links = document.createElement('div');
    links.className = 'v82-eval-nav-links';

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

    nav.appendChild(title);
    nav.appendChild(links);
    document.body.insertBefore(nav, document.body.firstChild);
  }

  function protectNormalUser(user){
    const role = lower(user && user.role);
    if(role === 'user'){
      document.body.innerHTML = '<div style="margin:24px;padding:16px;border:1px solid #fecaca;background:#fef2f2;color:#991b1b;border-radius:12px;font-weight:800;">Evaluation is available to Admin and Super Admin only. Redirecting to Chat...</div>';
      setTimeout(function(){ location.href = '/chat'; }, 800);
    }
  }

  function addWorkflowNote(){
    if(document.getElementById('v82EvaluationWorkflowNote')) return;
    const note = document.createElement('div');
    note.id = 'v82EvaluationWorkflowNote';
    note.className = 'v82-eval-note';
    note.textContent = 'Evaluation workflow: Upload workbooks, match intern, answer/review questions, then finalize. No workbook is updated until Finalize Evaluation is clicked.';
    const nav = document.getElementById('v82EvalNav');
    if(nav && nav.nextSibling){
      document.body.insertBefore(note, nav.nextSibling);
    }else{
      document.body.insertBefore(note, document.body.firstChild);
    }
  }

  function hideReasonBlocks(){
    document.querySelectorAll('.ai-reason,.ai-rationale,.reason,.reason-text,.rationale,.rationale-text,[data-ai-reason],[data-reason],[data-rationale]').forEach(function(el){
      el.style.display = 'none';
    });
  }

  async function boot(){
    const user = await getUser();
    ensureNav(user);
    protectNormalUser(user);
    if(lower(user && user.role) === 'user') return;
    addWorkflowNote();
    hideReasonBlocks();
  }

  document.addEventListener('DOMContentLoaded', boot);
  setTimeout(boot, 100);
  setTimeout(boot, 500);

  const mo = new MutationObserver(function(){
    clearTimeout(window.__v82EvalNativeTimer);
    window.__v82EvalNativeTimer = setTimeout(hideReasonBlocks, 100);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
'''

if "v82-evaluation-native-script" not in html:
    if "</body>" in html:
        html = html.replace("</body>", block + "\n</body>", 1)
    else:
        html += block
    page.write_text(html, encoding="utf-8")
    print(f"v0.82 applied: restored evaluation-native UI and added role-aware navbar. Updated: {page}")
else:
    print("v0.82 patch already applied.")

report = ROOT / "v82_evaluation_native_ui_report.txt"
report.write_text(
    "v0.82 applied.\n"
    "Removed the v0.81 forced review-panel layout.\n"
    "Kept evaluation as a native step workflow.\n"
    "Added role-aware navbar: Evaluation visible to Admin/Super Admin only.\n"
    f"Updated page: {page}\n",
    encoding="utf-8",
)
print(f"Report: {report}")
