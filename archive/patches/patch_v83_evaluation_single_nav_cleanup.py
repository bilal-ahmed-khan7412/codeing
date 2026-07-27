"""
Patch v0.83 - Evaluation single-navbar cleanup

Apply from the root of the app that serves /evaluation:
    python patch_v83_evaluation_single_nav_cleanup.py

Purpose:
- Fix duplicate/stacked headers on /evaluation caused by earlier navbar/UI patches.
- Keep the evaluation page's original workflow UI:
  Upload -> Match Intern -> Questions -> Review -> Download
- Do NOT force the tracker/chat review layout onto evaluation.
- Remove injected v81/v82 top bars, banners, debug buttons, and extra workflow notes.
- Add role-aware navigation using the existing/original evaluation header only.
- Admin/Super Admin see: Chat, Evaluation, Users, Logs, Tasks, Profile, Logout.
- Normal User sees: Chat, Profile, Logout and is redirected away from /evaluation.
- Do not change scoring, rubric, overall-only logic, finalize behavior, or workbook-write behavior.
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

# Remove earlier injected layout/navbar blocks that caused duplicate headers.
patterns = [
    r'\n?<!-- v0\.81 evaluation navbar \+ professional UI -->.*?<script id="v81-evaluation-ui-script">.*?</script>\s*',
    r'\n?<!-- v0\.82 evaluation-native navbar and UI polish -->.*?<script id="v82-evaluation-native-script">.*?</script>\s*',
    r'\n?<!-- v0\.83 evaluation single navbar cleanup -->.*?<script id="v83-evaluation-single-nav-script">.*?</script>\s*',
]
for pat in patterns:
    html = re.sub(pat, '\n', html, flags=re.S)

# Remove already-rendered static duplicates if previous patches wrote them into HTML directly.
html = re.sub(r'<div[^>]+id=["\']v81EvalNav["\'][\s\S]*?</div>\s*</div>\s*', '', html, flags=re.I)
html = re.sub(r'<div[^>]+id=["\']v82EvalNav["\'][\s\S]*?</div>\s*</div>\s*', '', html, flags=re.I)
html = re.sub(r'<div[^>]+id=["\']v82EvaluationWorkflowNote["\'][\s\S]*?</div>\s*', '', html, flags=re.I)

block = r'''

<!-- v0.83 evaluation single navbar cleanup -->
<style id="v83-evaluation-single-nav-style">
  /* Remove old injected nav/note/debug elements if they are produced dynamically. */
  #v81EvalNav,
  #v82EvalNav,
  #v82EvaluationWorkflowNote,
  #v78EvalDebugButton,
  #v79EvalDebugButton {
    display: none !important;
  }

  /* Keep page-specific evaluation workflow. Only polish existing header/nav. */
  .v83-eval-nav-links {
    display: flex;
    gap: 14px;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
  }

  .v83-eval-nav-links a {
    color: white !important;
    font-weight: 800 !important;
    text-decoration: underline;
  }

  .v83-eval-nav-links a:hover {
    opacity: 0.9;
  }

  .v83-eval-workflow-note {
    margin: 10px auto 16px;
    max-width: 980px;
    border: 1px solid #bfdbfe;
    background: #eff6ff;
    color: #1e3a8a;
    border-radius: 12px;
    padding: 10px 14px;
    font-weight: 700;
    font-size: 13px;
  }

  /* Keep private AI reason/rationale hidden. */
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
</style>
<script id="v83-evaluation-single-nav-script">
(function(){
  function norm(text){ return String(text || '').replace(/\s+/g, ' ').trim(); }
  function lower(text){ return norm(text).toLowerCase(); }

  async function getUser(){
    try{
      const r = await fetch('/api/me');
      const d = await r.json();
      return d.user || null;
    }catch(e){
      return null;
    }
  }

  function removeInjectedDuplicates(){
    document.querySelectorAll('#v81EvalNav,#v82EvalNav,#v82EvaluationWorkflowNote,#v78EvalDebugButton,#v79EvalDebugButton').forEach(function(el){
      el.remove();
    });

    // Remove duplicate blue "Intern Evaluation" banners if more than one exists.
    const candidates = Array.from(document.body.querySelectorAll('header, .v81-eval-nav, .v82-eval-nav, div')).filter(function(el){
      const t = lower(el.textContent);
      const style = window.getComputedStyle(el);
      const blueish = style.backgroundColor.includes('48, 84, 150') || style.backgroundColor.includes('31, 63, 117') || style.backgroundColor.includes('29, 78, 216');
      return t.includes('intern evaluation') && (blueish || el.id === 'v81EvalNav' || el.id === 'v82EvalNav');
    });
    if(candidates.length > 1){
      // Keep the first original-looking header, remove later injected duplicates.
      candidates.slice(1).forEach(function(el){
        if(el.id === 'v81EvalNav' || el.id === 'v82EvalNav' || lower(el.textContent).includes('evaluation workflow')) el.remove();
      });
    }
  }

  function findExistingHeader(){
    const headers = Array.from(document.querySelectorAll('header, .header, .topbar, .navbar, div')).filter(function(el){
      const t = lower(el.textContent);
      const childCount = el.children.length;
      return t.includes('intern evaluation') && childCount <= 20;
    });
    return headers[0] || document.querySelector('header') || document.body.firstElementChild;
  }

  function ensureSingleNav(user){
    const role = lower(user && user.role);
    const isAdmin = role === 'admin' || role === 'super admin';
    const header = findExistingHeader();
    if(!header) return;

    // Remove all links inside the chosen header, then rebuild role-aware nav.
    header.querySelectorAll('a').forEach(function(a){ a.remove(); });

    let linkBox = header.querySelector('.v83-eval-nav-links');
    if(!linkBox){
      linkBox = document.createElement('div');
      linkBox.className = 'v83-eval-nav-links';
      header.appendChild(linkBox);
    }
    linkBox.innerHTML = '';

    function add(href, text){
      const a = document.createElement('a');
      a.href = href;
      a.textContent = text;
      linkBox.appendChild(a);
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
  }

  function protectNormalUser(user){
    const role = lower(user && user.role);
    if(role === 'user'){
      document.body.innerHTML = '<div style="margin:24px;padding:16px;border:1px solid #fecaca;background:#fef2f2;color:#991b1b;border-radius:12px;font-weight:800;">Evaluation is available to Admin and Super Admin only. Redirecting to Chat...</div>';
      setTimeout(function(){ location.href = '/chat'; }, 900);
    }
  }

  function ensureOneWorkflowNote(){
    document.querySelectorAll('.v83-eval-workflow-note').forEach(function(el, idx){ if(idx > 0) el.remove(); });
    if(document.querySelector('.v83-eval-workflow-note')) return;

    const note = document.createElement('div');
    note.className = 'v83-eval-workflow-note';
    note.textContent = 'Evaluation workflow: Upload workbooks, match intern, answer/review questions, then finalize. No workbook is updated until Finalize Evaluation is clicked.';

    const header = findExistingHeader();
    if(header && header.parentElement){
      header.parentElement.insertBefore(note, header.nextSibling);
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
    removeInjectedDuplicates();
    ensureSingleNav(user);
    protectNormalUser(user);
    if(lower(user && user.role) === 'user') return;
    ensureOneWorkflowNote();
    hideReasonBlocks();
  }

  document.addEventListener('DOMContentLoaded', boot);
  setTimeout(boot, 100);
  setTimeout(boot, 500);
  setTimeout(boot, 1200);

  const mo = new MutationObserver(function(){
    clearTimeout(window.__v83EvalNavTimer);
    window.__v83EvalNavTimer = setTimeout(function(){
      removeInjectedDuplicates();
      hideReasonBlocks();
    }, 120);
  });
  mo.observe(document.documentElement, {childList:true, subtree:true});
})();
</script>
'''

if "v83-evaluation-single-nav-script" not in html:
    if "</body>" in html:
        html = html.replace("</body>", block + "\n</body>", 1)
    else:
        html += block

page.write_text(html, encoding="utf-8")

report = ROOT / "v83_evaluation_single_nav_report.txt"
report.write_text(
    "v0.83 applied.\n"
    "Removed v81/v82 injected duplicate nav/layout blocks.\n"
    "Kept evaluation-native workflow UI.\n"
    "Role-aware links are rebuilt only inside existing evaluation header.\n"
    f"Updated: {page}\n",
    encoding="utf-8",
)

print("v0.83 applied: duplicate evaluation headers cleaned, native evaluation UI preserved.")
print(f"Updated: {page}")
print(f"Report: {report}")
